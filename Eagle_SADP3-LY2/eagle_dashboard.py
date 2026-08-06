import tkinter as tk
import serial
import time

# --------------------------
# LIN
# --------------------------

ser = serial.Serial("/dev/serial0", 115200, timeout=0.2)

def send(cmd, delay=0.05):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()

print(send("V", 0.2))
send("S3")
send("O")

# --------------------------
# SENSOR (SADP3-LY2, LDF frame 0x07)
# --------------------------

FRAME_SLAVE  = "07"   # SADP_Stat_LIN — slave publishes, 8 bytes
FRAME_MASTER = "05"   # Placeholder   — master sends 8 zero bytes
PLACEHOLDER  = "0000000000000000"
ERR_8  = (254, 255)
ERR_11 = (2046, 2047)

def read_sensor():
    send(f"T{FRAME_MASTER}{PLACEHOLDER}")
    rx = send(f"r{FRAME_SLAVE}", 0.1)

    if not rx.startswith("M"):
        return None

    try:
        h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
        i = h.find(FRAME_SLAVE.upper())
        if i < 0 or len(h) - i - 2 < 16:
            return None

        d = bytes.fromhex(h[i + 2 : i + 18])

        dew_raw = d[0]
        rh_raw  = d[1]
        amb_raw = d[2]
        dew_hi  = d[3] | ((d[4] & 0x07) << 8)
        amb_hi  = ((d[4] >> 4) & 0x0F) | ((d[5] & 0x7F) << 4)
        rs_err  = (d[7] >> 7) & 0x01

        temp    = None if amb_hi  in ERR_11 else amb_hi  * 0.1 - 40.0
        temp_lo = None if amb_raw in ERR_8  else amb_raw * 0.5 - 40.0
        dew     = None if dew_hi  in ERR_11 else dew_hi  * 0.1 - 40.0
        rh      = None if rh_raw  in ERR_8  else rh_raw  * 0.5

        return {
            "temp":   temp if temp is not None else temp_lo,
            "dew":    dew,
            "rh":     rh,
            "rs_err": rs_err,
        }

    except Exception as e:
        print(e)
        return None

# --------------------------
# Comfort / color
# --------------------------

THRESHOLDS = [
    (10,  "#3498db", "COLD"),
    (20,  "#1abc9c", "COOL"),
    (26,  "#2ecc71", "COMFORTABLE"),
    (35,  "#e67e22", "WARM"),
    (999, "#e74c3c", "HOT"),
]
COLOR_NA = "#7f8c8d"

def temp_theme(t):
    if t is None:
        return COLOR_NA, "NO DATA"
    for limit, color, label in THRESHOLDS:
        if t < limit:
            return color, label
    return "#e74c3c", "HOT"

# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title("SADP3-LY2")
root.attributes("-fullscreen", True)

BG = "#2ecc71"
root.configure(bg=BG)

container = tk.Frame(root, bg=BG)
container.place(relx=0.5, rely=0.5, anchor="center")

title_lbl = tk.Label(
    container,
    text="SADP3-LY2",
    font=("Arial", 30, "bold"),
    fg="white", bg=BG,
)
title_lbl.grid(row=0, column=0, columnspan=3, pady=(0, 24))

# ── Value column factory ─────────────────────────────────────────────────────

def make_col(parent, label_text, unit_text, col):
    f = tk.Frame(parent, bg=BG, padx=40)
    f.grid(row=1, column=col, padx=20)
    lbl = tk.Label(f, text=label_text, font=("Arial", 22, "bold"), fg="white", bg=BG)
    lbl.pack()
    val = tk.Label(f, text="--", font=("Arial", 88, "bold"), fg="white", bg=BG)
    val.pack()
    unt = tk.Label(f, text=unit_text, font=("Arial", 20), fg="white", bg=BG)
    unt.pack()
    return f, lbl, val, unt

t_frame,  t_title,  t_val,  t_unit  = make_col(container, "Temperature", "°C",  0)
rh_frame, rh_title, rh_val, rh_unit = make_col(container, "Humidity",    "%RH", 1)
dp_frame, dp_title, dp_val, dp_unit = make_col(container, "Dew Point",   "°C",  2)

quality_lbl = tk.Label(
    container,
    text="--",
    font=("Arial", 42, "bold"),
    fg="white", bg=BG,
)
quality_lbl.grid(row=2, column=0, columnspan=3, pady=14)

status_lbl = tk.Label(
    container,
    text="Status: --",
    font=("Arial", 20),
    fg="white", bg=BG,
)
status_lbl.grid(row=3, column=0, columnspan=3)

clock_lbl = tk.Label(
    container,
    text="",
    font=("Arial", 18),
    fg="white", bg=BG,
)
clock_lbl.grid(row=4, column=0, columnspan=3, pady=8)

ALL_WIDGETS = [
    container, title_lbl, quality_lbl, status_lbl, clock_lbl,
    t_frame,  t_title,  t_val,  t_unit,
    rh_frame, rh_title, rh_val, rh_unit,
    dp_frame, dp_title, dp_val, dp_unit,
]

def set_bg(color):
    root.configure(bg=color)
    for w in ALL_WIDGETS:
        w.configure(bg=color)

# ── Update loop ──────────────────────────────────────────────────────────────

def update():
    data  = read_sensor()
    temp  = data["temp"] if data else None
    color, label = temp_theme(temp)

    set_bg(color)
    quality_lbl.config(text=label)

    if data:
        t_val.config(text=f"{data['temp']:.1f}" if data["temp"] is not None else "--")
        rh_val.config(text=f"{data['rh']:.1f}"  if data["rh"]  is not None else "--")
        dp_val.config(text=f"{data['dew']:.1f}" if data["dew"] is not None else "--")
        status_lbl.config(text=f"RsErr: {data['rs_err']}")
    else:
        for v in (t_val, rh_val, dp_val):
            v.config(text="--")
        status_lbl.config(text="Status: --")

    clock_lbl.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, update)

root.bind("<Escape>", lambda e: root.destroy())
update()

try:
    root.mainloop()
finally:
    send("C")
    ser.close()
