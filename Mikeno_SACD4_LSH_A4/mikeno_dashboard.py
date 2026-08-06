import tkinter as tk
import serial
import time

# --------------------------
# LIN / MANI LDF
# --------------------------

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

FRAME_MASTER = "1D"  # SACD_Master_Frame
FRAME_SENSOR = "1F"  # SACD_Sensor_Frame

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

def encode_master_frame(
    measure_mode=1,      # 0=NoMeasurement, 1=DrivingMode, 2=ParkingMode
    debounce1_s=20,
    debounce2_s=10,
    measure_rate_s=300,  # phys = raw*2 + 2
    observation_min=720,
    threshold1_ppm=20000,  # phys = raw*250
    threshold2_ppm=30000,  # phys = raw*250
    master_pressure_mbar=1000,  # phys = raw*10 + 500
):
    deb1_raw = max(0, min(255, int(debounce1_s)))
    deb2_raw = max(0, min(255, int(debounce2_s)))
    rate_raw = max(0, min(255, int((measure_rate_s - 2) / 2)))
    obs_raw = max(0, min(1023, int(observation_min)))
    thr1_raw = max(0, min(255, int(threshold1_ppm / 250)))
    thr2_raw = max(0, min(255, int(threshold2_ppm / 250)))
    p_raw = max(0, min(255, int((master_pressure_mbar - 500) / 10)))

    v = 0
    v = set_bits(v, 0, 2, measure_mode)
    v = set_bits(v, 2, 8, deb1_raw)
    v = set_bits(v, 10, 8, deb2_raw)
    v = set_bits(v, 18, 8, rate_raw)
    v = set_bits(v, 26, 10, obs_raw)
    v = set_bits(v, 36, 8, thr1_raw)
    v = set_bits(v, 44, 8, thr2_raw)
    v = set_bits(v, 52, 8, p_raw)

    return v.to_bytes(8, "little").hex().upper()

def send_master_config(mode=1):
    payload = encode_master_frame(measure_mode=mode)
    send(f"T{FRAME_MASTER}8{payload}")

def decode_sensor(rx):
    if not rx.startswith("M"):
        return None

    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find(FRAME_SENSOR)
    if i < 0 or len(h) < i + 2 + 16:
        return None

    payload = h[i + 2:i + 18]
    b = bytes.fromhex(payload)
    v = int.from_bytes(b, "little")

    gas_raw = get_bits(v, 0, 16)
    alarm = get_bits(v, 16, 2)
    temp_raw = get_bits(v, 18, 8)
    hum_raw = get_bits(v, 26, 8)
    sp_raw = get_bits(v, 34, 8)
    fc = get_bits(v, 42, 4)
    ste = get_bits(v, 46, 1)
    re = get_bits(v, 47, 1)

    def dec_temp(r):
        if r in (0xFD, 0xFE, 0xFF):
            return None
        return r * 0.5 - 40.0

    def dec_hum(r):
        if r in (0xFD, 0xFE, 0xFF):
            return None
        return r * 0.5

    def dec_press(r):
        if r in (0xFD, 0xFE, 0xFF):
            return None
        return r * 10 + 500

    if gas_raw in (0xFFFD, 0xFFFE, 0xFFFF):
        gas_ppm = None
    else:
        gas_ppm = gas_raw

    alarm_txt = "ALARM" if alarm == 2 else "OK"

    return {
        "gas_ppm": gas_ppm,
        "alarm": alarm_txt,
        "temp_c": dec_temp(temp_raw),
        "rh": dec_hum(hum_raw),
        "press_mbar": dec_press(sp_raw),
        "fc": fc,
        "ste": ste,
        "re": re,
    }

# --------------------------
# UI
# --------------------------

def quality_color(ppm):
    if ppm is None:
        return "#7f8c8d", "NO DATA"
    if ppm < 1000:
        return "#2ecc71", "GOOD"
    if ppm < 2000:
        return "#f1c40f", "ELEVATED"
    if ppm < 5000:
        return "#e67e22", "HIGH"
    return "#e74c3c", "DANGER"

root = tk.Tk()
root.title("MANI CO2")
root.attributes("-fullscreen", True)

bg = "#2ecc71"
root.configure(bg=bg)

frame = tk.Frame(root, bg=bg)
frame.place(relx=0.5, rely=0.5, anchor="center")

title = tk.Label(frame, text="CO2", font=("Arial", 34, "bold"), fg="white", bg=bg)
title.pack()

value = tk.Label(frame, text="--", font=("Arial", 140, "bold"), fg="white", bg=bg)
value.pack()

unit = tk.Label(frame, text="ppm", font=("Arial", 28), fg="white", bg=bg)
unit.pack()

quality = tk.Label(frame, text="--", font=("Arial", 42, "bold"), fg="white", bg=bg)
quality.pack(pady=10)

status = tk.Label(frame, text="Alarm: --", font=("Arial", 22), fg="white", bg=bg)
status.pack()

details = tk.Label(frame, text="T: --  RH: --  P: --", font=("Arial", 20), fg="white", bg=bg)
details.pack()

errors = tk.Label(frame, text="STE: --  RE: --  FC: --", font=("Arial", 18), fg="white", bg=bg)
errors.pack()

clock = tk.Label(frame, text="", font=("Arial", 18), fg="white", bg=bg)
clock.pack(pady=10)

widgets = (frame, title, value, unit, quality, status, details, errors, clock)

def set_color(color):
    root.configure(bg=color)
    for w in widgets:
        w.configure(bg=color)

def update():
    send_master_config(mode=1)
    rx = send(f"r{FRAME_SENSOR}", 0.15)
    data = decode_sensor(rx)

    ppm = data["gas_ppm"] if data else None
    color, label = quality_color(ppm)
    set_color(color)
    quality.config(text=label)

    if data and ppm is not None:
        value.config(text=str(ppm))
        status.config(text=f"Alarm: {data['alarm']}")
        t = "--" if data["temp_c"] is None else f"{data['temp_c']:.1f}C"
        rh = "--" if data["rh"] is None else f"{data['rh']:.1f}%"
        p = "--" if data["press_mbar"] is None else f"{data['press_mbar']} mbar"
        details.config(text=f"T: {t}  RH: {rh}  P: {p}")
        errors.config(text=f"STE: {data['ste']}  RE: {data['re']}  FC: {data['fc']}")
    else:
        value.config(text="--")
        status.config(text="Alarm: --")
        details.config(text="T: --  RH: --  P: --")
        errors.config(text="STE: --  RE: --  FC: --")

    clock.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, update)

root.bind("<Escape>", lambda e: root.destroy())

print(send("V", 0.2))
send("S3")
send("O")
send_master_config(mode=1)
time.sleep(1)

update()

try:
    root.mainloop()
finally:
    send_master_config(mode=0)
    send("C")
    ser.close()
