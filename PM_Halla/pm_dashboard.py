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
# SENSOR
# --------------------------

def read_sensor():

    send("T1D101")

    rx = send("r1A", 0.1)

    if not rx.startswith("M"):
        return None, "No Data"

    try:
        hexstr = "".join(
            c for c in rx
            if c in "0123456789ABCDEFabcdef"
        ).upper()

        idx = hexstr.find("1A")

        if idx < 0:
            return None, "No Data"

        payload = hexstr[idx + 2:]

        if len(payload) < 10:
            return None, "No Data"

        data = bytes.fromhex(payload[:10])

        b0, b1, b2, b3, b4 = data

        status_id = (b0 >> 1) & 0x07

        status_map = {
            0: "Init",
            1: "Normal",
            2: "Limited",
            3: "Standby",
            4: "Error"
        }

        pm25 = b1 | ((b2 & 0x03) << 8)

        if pm25 == 1021:
            return None, "Standby"

        if pm25 == 1022:
            return None, "Init"

        return pm25, status_map.get(status_id, "Unknown")

    except Exception as e:
        print(e)
        return None, "Error"

# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title("PM2.5")
root.attributes("-fullscreen", True)

background = "#2ecc71"
root.configure(bg=background)

frame = tk.Frame(root, bg=background)
frame.place(relx=0.5, rely=0.5, anchor="center")

title = tk.Label(
    frame,
    text="PM2.5",
    font=("Arial", 34, "bold"),
    fg="white",
    bg=background
)
title.pack()

value = tk.Label(
    frame,
    text="--",
    font=("Arial", 140, "bold"),
    fg="white",
    bg=background
)
value.pack()

unit = tk.Label(
    frame,
    text="µg/m³",
    font=("Arial", 28),
    fg="white",
    bg=background
)
unit.pack()

quality = tk.Label(
    frame,
    text="GOOD",
    font=("Arial", 42, "bold"),
    fg="white",
    bg=background
)
quality.pack(pady=10)

status_label = tk.Label(
    frame,
    text="Status: --",
    font=("Arial", 22),
    fg="white",
    bg=background
)
status_label.pack()

clock = tk.Label(
    frame,
    text="",
    font=("Arial", 18),
    fg="white",
    bg=background
)
clock.pack(pady=10)

def set_color(color):

    root.configure(bg=color)
    frame.configure(bg=color)

    widgets = (
        title,
        value,
        unit,
        quality,
        status_label,
        clock
    )

    for widget in widgets:
        widget.configure(bg=color)

def update():

    pm25, sensor_status = read_sensor()

    if pm25 is not None:

        value.config(text=str(pm25))
        status_label.config(text=f"Status: {sensor_status}")

        if pm25 <= 12:
            set_color("#2ecc71")
            quality.config(text="GOOD")

        elif pm25 <= 35:
            set_color("#f1c40f")
            quality.config(text="MODERATE")

        elif pm25 <= 55:
            set_color("#e67e22")
            quality.config(text="UNHEALTHY")

        else:
            set_color("#e74c3c")
            quality.config(text="DANGER")

    else:
        value.config(text="--")
        status_label.config(text=f"Status: {sensor_status}")

    clock.config(
        text=time.strftime("%H:%M:%S")
    )

    root.after(1000, update)

root.bind("<Escape>", lambda e: root.destroy())

update()

try:
    root.mainloop()
finally:
    send("T1D100")
    send("C")
    ser.close()

