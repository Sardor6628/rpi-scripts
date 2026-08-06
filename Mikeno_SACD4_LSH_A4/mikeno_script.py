import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

# ── LDF constants (SACD4-LCH1_D3.ldf, ICO2 on Klima_LIN6) ──────────────────
FRAME_MASTER = "1D"   # ICO2e_01 (master → slave, 8 bytes)
FRAME_SLAVE  = "1F"   # ICO2s_01 (slave → master, 8 bytes)


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


def encode_master(messvorgabe=1, status_kabine=0, luftdruck_2=600,
                  messzyklus1=0, messzyklus2=0):
    """Build the 8-byte ICO2e_01 master frame payload.

    Signal layout (bit offsets from LDF):
        ICO2_Messvorgabe   :  0, 3 bits   (0=off, 1=Fahrbetrieb, 2=Parkbetrieb)
        ICO2_Status_Kabine :  3, 3 bits
        ICO2_Luftdruck_2   :  6, 10 bits  (phys = raw + 400 mbar)
        ICO2_Messzyklus1   : 16, 8 bits
        ICO2_Messzyklus2   : 24, 8 bits
    """
    v = 0
    v = set_bits(v, 0, 3, messvorgabe)
    v = set_bits(v, 3, 3, status_kabine)
    v = set_bits(v, 6, 10, luftdruck_2)
    v = set_bits(v, 16, 8, messzyklus1)
    v = set_bits(v, 24, 8, messzyklus2)
    return v.to_bytes(8, "little").hex().upper()


def send_master_config(messvorgabe=1, luftdruck_2=600):
    payload = encode_master(messvorgabe=messvorgabe, luftdruck_2=luftdruck_2)
    resp = send(f"T{FRAME_MASTER}8{payload}")
    return resp


def decode_slave(rx):
    """Decode the 8-byte ICO2s_01 slave frame.

    Signal layout (bit offsets from LDF):
        ICO2_CO2_Wert      :  0, 10 bits  (0.01 kPa per step = 100 ppm)
        ICO2_Alarm         : 10,  2 bits   (0=OK, 1=Gradient, 2=Limit)
        ICO2_BZ            : 12,  4 bits
        ICO2_Gradient      : 16, 10 bits   (phys = raw*100 - 50000)
        ICO2_Luftdruck     : 26, 10 bits   (phys = raw + 400 mbar)
        ICO2_ResponseError : 36,  1 bit
        ICO2_defekt        : 37,  1 bit
        ICO2_Laufzeit      : 40, 16 bits   (phys = raw*10 s)
    """
    if not rx.startswith("M"):
        return None

    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find(FRAME_SLAVE)
    if i < 0 or len(h) < i + 2 + 16:
        return None

    payload = h[i + 2:i + 18]
    v = int.from_bytes(bytes.fromhex(payload), "little")

    co2_raw = get_bits(v, 0, 10)
    alarm   = get_bits(v, 10, 2)
    bz      = get_bits(v, 12, 4)
    grad    = get_bits(v, 16, 10)
    press   = get_bits(v, 26, 10)
    re      = get_bits(v, 36, 1)
    defect  = get_bits(v, 37, 1)
    rt_raw  = get_bits(v, 40, 16)

    co2_ppm = None if co2_raw in (1022, 1023) else co2_raw * 100
    grad_v  = None if grad in (1022, 1023) else grad * 100 - 50000
    p_mbar  = None if press in (1021, 1022, 1023) else press + 400
    rt_s    = None if rt_raw in (65534, 65535) else rt_raw * 10

    alarm_map = {0: "OK", 1: "Gradient", 2: "Limit"}

    return {
        "co2_ppm": co2_ppm,
        "co2_raw": co2_raw,
        "alarm": alarm_map.get(alarm, str(alarm)),
        "bz": bz,
        "gradient": grad_v,
        "press_mbar": p_mbar,
        "runtime_s": rt_s,
        "defect": defect,
        "resp_err": re,
    }


# ── Init LIN bus (19.2 kbps per LDF) ────────────────────────────────────────
print(send("V", 0.2))
send("S3")
send("O")

# First master frame + settle time
print("CTRL:", send_master_config(messvorgabe=1, luftdruck_2=600))
time.sleep(1)

try:
    while True:
        # LDF schedule: ICO2e_01 (100ms) then ICO2s_01 (100ms)
        # Must send master frame before each slave read
        send_master_config(messvorgabe=1, luftdruck_2=600)
        time.sleep(0.1)  # 100ms inter-frame delay per schedule table

        rx = send(f"r{FRAME_SLAVE}", 0.15)
        data = decode_slave(rx)

        ts = datetime.now().strftime("%H:%M:%S")
        if data:
            co2 = "N/A" if data["co2_ppm"] is None else f"{data['co2_ppm']} ppm"
            grad = "N/A" if data["gradient"] is None else str(data["gradient"])
            p = "N/A" if data["press_mbar"] is None else f"{data['press_mbar']} mbar"
            rt = "N/A" if data["runtime_s"] is None else f"{data['runtime_s']} s"
            print(
                f"{ts}  CO2={co2}  Alarm={data['alarm']}  "
                f"Grad={grad}  P={p}  RT={rt}  "
                f"Def={data['defect']}  RE={data['resp_err']}"
            )
        else:
            print(f"{ts}  no valid frame  raw={rx!r}")

        time.sleep(0.1)  # 100ms before next schedule cycle

except KeyboardInterrupt:
    print("\nStopping...")
    send_master_config(messvorgabe=0, luftdruck_2=600)
    send("C")
    ser.close()
