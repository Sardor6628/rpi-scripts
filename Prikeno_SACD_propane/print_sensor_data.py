import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

# ── LDF constants (prikeno.sdf / LIN_SACD, LIN 2.2, 19.2 kbps) ──────────────
FRAME_MASTER = "1D"   # SACD_Master_Frame (master → slave, 8 bytes)
FRAME_SLAVE  = "1F"   # SACD_Sensor_Frame (slave → master, 8 bytes)

# Lower explosion limit of propane (2.1 vol%) used to express ppm as %LEL.
PROPANE_LEL_PPM = 21000


def send(cmd, delay=0.06):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()


def get_bits(v, start, length):
    return (v >> start) & ((1 << length) - 1)


def set_bits(v, start, length, val):
    mask = ((1 << length) - 1) << start
    return (v & ~mask) | ((val & ((1 << length) - 1)) << start)


def pressure_raw(mbar):
    """PressureEnc: phys = raw*10 + 500 mbar, valid raw 0..70."""
    if mbar is None:
        return 0xFF  # Init → sensor uses SensorPressure or its 1000 mbar default
    return max(0, min(70, round((mbar - 500) / 10)))


def encode_master(measure_mode=1, pressure_mbar=1000, debounce1=0xFF,
                  debounce2=0xFF, measure_rate=0xFF, observation_time=0x3FF,
                  threshold1=0xFF, threshold2=0xFF):
    """Build the 8-byte SACD_Master_Frame payload.

    Signal layout (bit offsets from LDF):
        MeasureMode     :  0,  2 bits  (0=NoMeasurement, 1=DrivingMode, 2=ParkingMode)
        Debounce1       :  2,  8 bits  (s)
        Debounce2       : 10,  8 bits  (s)
        MeasureRate     : 18,  8 bits  (phys = raw*2 + 2 s)
        ObservationTime : 26, 10 bits  (min)
        Threshold1      : 36,  8 bits  (phys = raw*250 ppm)
        Threshold2      : 44,  8 bits  (phys = raw*250 ppm)
        MasterPressure  : 52,  8 bits  (phys = raw*10 + 500 mbar)

    Debounce/rate/time/threshold default to Init (0xFF / 0x3FF); the sensor then
    applies its own defaults (20 s, 10 s, 30 s, 720 min, 3250 ppm, 4250 ppm).
    """
    v = 0
    v = set_bits(v, 0, 2, measure_mode)
    v = set_bits(v, 2, 8, debounce1)
    v = set_bits(v, 10, 8, debounce2)
    v = set_bits(v, 18, 8, measure_rate)
    v = set_bits(v, 26, 10, observation_time)
    v = set_bits(v, 36, 8, threshold1)
    v = set_bits(v, 44, 8, threshold2)
    v = set_bits(v, 52, 8, pressure_raw(pressure_mbar))
    return v.to_bytes(8, "little").hex().upper()


def send_master_config(measure_mode=1, pressure_mbar=1000):
    payload = encode_master(measure_mode=measure_mode, pressure_mbar=pressure_mbar)
    return send(f"T{FRAME_MASTER}8{payload}")


def decode_slave(rx):
    """Decode the 8-byte SACD_Sensor_Frame.

    Signal layout (bit offsets from LDF):
        GasConcentration : 0,  16 bits  (ppm, 1 ppm/step)
        GasAlarm         : 16,  2 bits  (0=NoAlarm, 2=Alarm)
        Temperature      : 18,  8 bits  (phys = raw*0.5 - 40 degC)
        Humidity         : 26,  8 bits  (phys = raw*0.5 %RH)
        SensorPressure   : 34,  8 bits  (phys = raw*10 + 500 mbar)
        FrameCounter     : 42,  4 bits
        SelfTestError    : 46,  1 bit
        ResponseError    : 47,  1 bit
    """
    if not rx.startswith("M"):
        return None

    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find(FRAME_SLAVE)
    if i < 0 or len(h) < i + 2 + 16:
        return None

    payload = h[i + 2:i + 18]
    v = int.from_bytes(bytes.fromhex(payload), "little")

    gas_raw   = get_bits(v, 0, 16)
    alarm     = get_bits(v, 16, 2)
    temp_raw  = get_bits(v, 18, 8)
    hum_raw   = get_bits(v, 26, 8)
    press_raw = get_bits(v, 34, 8)
    counter   = get_bits(v, 42, 4)
    self_test = get_bits(v, 46, 1)
    resp_err  = get_bits(v, 47, 1)

    # 0xFD/0xFE/0xFF (0xFFFD.. for 16 bit) = NotAvailable / Error / Init.
    ppm    = None if gas_raw in (0xFFFD, 0xFFFE, 0xFFFF) else gas_raw
    temp_c = None if temp_raw in (0xFD, 0xFE, 0xFF) else temp_raw * 0.5 - 40
    hum_pc = None if hum_raw in (0xFD, 0xFE, 0xFF) else hum_raw * 0.5
    p_mbar = None if press_raw in (0xFD, 0xFE, 0xFF) else press_raw * 10 + 500

    return {
        "ppm": ppm,
        "gas_raw": gas_raw,
        "lel_pct": None if ppm is None else ppm / PROPANE_LEL_PPM * 100,
        "alarm": "Alarm" if alarm == 2 else "NoAlarm",
        "temp_c": temp_c,
        "hum_pct": hum_pc,
        "press_mbar": p_mbar,
        "counter": counter,
        "self_test_error": self_test,
        "resp_err": resp_err,
    }


# ── Init LIN bus (19.2 kbps per LDF) ────────────────────────────────────────
print(send("V", 0.2))
send("S3")
send("O")

# First master frame + settle time
print("CTRL:", send_master_config(measure_mode=1))
time.sleep(1)

try:
    while True:
        # LDF sch_normal: SACD_Master_Frame then SACD_Sensor_Frame, 10 ms apart.
        send_master_config(measure_mode=1)
        time.sleep(0.01)

        rx = send(f"r{FRAME_SLAVE}", 0.15)
        data = decode_slave(rx)

        ts = datetime.now().strftime("%H:%M:%S")
        if data:
            gas = "N/A" if data["ppm"] is None else f"{data['ppm']} ppm"
            lel = "N/A" if data["ppm"] is None else f"{data['lel_pct']:.1f} %LEL"
            t = "N/A" if data["temp_c"] is None else f"{data['temp_c']:.1f}C"
            rh = "N/A" if data["hum_pct"] is None else f"{data['hum_pct']:.1f}%"
            p = "N/A" if data["press_mbar"] is None else f"{data['press_mbar']} mbar"
            # Tcav/RHcav are inside the self-heated measuring cavity, not ambient.
            print(
                f"{ts}  C3H8={gas} ({lel})  Alarm={data['alarm']}  "
                f"Tcav={t}  RHcav={rh}  P={p}  "
                f"FC={data['counter']}  ST={data['self_test_error']}  RE={data['resp_err']}"
            )
        else:
            print(f"{ts}  no valid frame  raw={rx!r}")

        time.sleep(1)  # sensor measures at 1 s in DrivingMode

except KeyboardInterrupt:
    print("\nStopping...")
    send_master_config(measure_mode=0)
    send("C")
    ser.close()
