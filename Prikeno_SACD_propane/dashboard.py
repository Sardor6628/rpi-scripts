import tkinter as tk
import serial
import time

# --------------------------
# LIN / SACD propane sensor (prikeno.sdf, channel LIN_SACD)
# --------------------------

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

FRAME_MASTER = "1D"  # SACD_Master_Frame (master → slave, 8 bytes)
FRAME_SLAVE  = "1F"  # SACD_Sensor_Frame (slave → master, 8 bytes)

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
    send(f"T{FRAME_MASTER}8{payload}")


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
        "lel_pct": None if ppm is None else ppm / PROPANE_LEL_PPM * 100,
        "alarm": alarm == 2,
        "temp_c": temp_c,
        "hum_pct": hum_pc,
        "press_mbar": p_mbar,
        "counter": counter,
        "self_test_error": self_test,
        "resp_err": resp_err,
    }


# --------------------------
# UI
# --------------------------

def quality_color(ppm, alarm):
    if ppm is None:
        return "#7f8c8d", "NO DATA"
    if alarm:
        return "#e74c3c", "GAS ALARM"
    lel = ppm / PROPANE_LEL_PPM * 100
    if lel < 5:
        return "#2ecc71", "CLEAN"
    if lel < 10:
        return "#f1c40f", "TRACE"
    if lel < 20:
        return "#e67e22", "ELEVATED"
    return "#e74c3c", "DANGER"


root = tk.Tk()
root.title("Propane – Prikeno")
root.attributes("-fullscreen", True)
# XWayland ignores -fullscreen set before the window is mapped, so pin the
# geometry and re-assert it once the session has placed the window.
root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
root.after(500, lambda: root.attributes("-fullscreen", True))

bg = "#2ecc71"
root.configure(bg=bg)

frame = tk.Frame(root, bg=bg)
frame.place(relx=0.5, rely=0.5, anchor="center")

title = tk.Label(frame, text="SACD C3H8", font=("Arial", 34, "bold"), fg="white", bg=bg)
title.pack()

value = tk.Label(frame, text="--", font=("Arial", 140, "bold"), fg="white", bg=bg)
value.pack()

unit = tk.Label(frame, text="ppm", font=("Arial", 28), fg="white", bg=bg)
unit.pack()

quality = tk.Label(frame, text="--", font=("Arial", 42, "bold"), fg="white", bg=bg)
quality.pack(pady=10)

lel = tk.Label(frame, text="--", font=("Arial", 26), fg="white", bg=bg)
lel.pack()

widgets = (frame, title, value, unit, quality, lel)


def set_color(color):
    root.configure(bg=color)
    for w in widgets:
        w.configure(bg=color)


def update():
    # LDF sch_normal: SACD_Master_Frame then SACD_Sensor_Frame, 10 ms apart.
    send_master_config(measure_mode=1)
    time.sleep(0.01)

    rx = send(f"r{FRAME_SLAVE}", 0.15)
    data = decode_slave(rx)

    ppm = data["ppm"] if data else None
    color, label = quality_color(ppm, data["alarm"] if data else False)
    set_color(color)
    quality.config(text=label)

    if data and ppm is not None:
        value.config(text=str(ppm))
        lel.config(text=f"{data['lel_pct']:.1f} % LEL")
    else:
        value.config(text="--")
        lel.config(text="--")

    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())

# ── Init LIN bus ─────────────────────────────────────────────────────────────
print(send("V", 0.2))
send("S3")
send("O")
send_master_config(measure_mode=1)
time.sleep(1)

update()

try:
    root.mainloop()
finally:
    send_master_config(measure_mode=0)
    send("C")
    ser.close()
