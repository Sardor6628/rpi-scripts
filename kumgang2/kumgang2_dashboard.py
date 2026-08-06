import tkinter as tk
import serial
import time
from sensirion_i2c_driver import I2cConnection
from sensirion_sensorbridge_i2c_driver import SensorBridgeI2cDevice
from sensirion_i2c_sht.sht4x import Sht4xI2cDevice
from sensirion_sensorbridge_driver import SensorBridge

# --------------------------
# SENSORBRIDGE
# --------------------------

SERIAL_PORTS = ['/dev/ttyUSB0', '/dev/ttyUSB1']
BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
SHT4X_ADDR = 0x44


def find_bridge():
    for port in SERIAL_PORTS:
        try:
            ser = serial.Serial(port, BAUDRATE, timeout=1)
            bridge = SensorBridge(ser)
            print(f"SensorBridge found on {port}")
            return bridge
        except (serial.SerialException, OSError):
            continue
    return None


bridge = find_bridge()
if bridge is None:
    print("ERROR: No SensorBridge found.")
    exit(1)

bridge.set_i2c_frequency(0, I2C_FREQ)
bridge.set_supply_voltage(0, SUPPLY_V)
bridge.switch_supply_on(0)
time.sleep(0.5)

i2c = SensorBridgeI2cDevice(bridge, port=0, slave_address=SHT4X_ADDR)
sensor = Sht4xI2cDevice(I2cConnection(i2c))

# --------------------------
# SENSOR
# --------------------------


def read_sensor():
    try:
        temp, hum = sensor.single_shot_measurement()
        return float(str(temp).split()[0]), float(str(hum).split()[0]), "Normal"
    except Exception as e:
        print(e)
        return None, None, "Error"


# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title("Kumgang2 - Temperature & Humidity")
root.attributes("-fullscreen", True)

background = "#3498db"
root.configure(bg=background)

frame = tk.Frame(root, bg=background)
frame.place(relx=0.5, rely=0.5, anchor="center")

title = tk.Label(
    frame,
    text="Temperature / Humidity",
    font=("Arial", 34, "bold"),
    fg="white",
    bg=background
)
title.pack()

temp_value = tk.Label(
    frame,
    text="--",
    font=("Arial", 100, "bold"),
    fg="white",
    bg=background
)
temp_value.pack()

temp_unit = tk.Label(
    frame,
    text="°C",
    font=("Arial", 28),
    fg="white",
    bg=background
)
temp_unit.pack()

hum_value = tk.Label(
    frame,
    text="--",
    font=("Arial", 80, "bold"),
    fg="white",
    bg=background
)
hum_value.pack(pady=(20, 0))

hum_unit = tk.Label(
    frame,
    text="% RH",
    font=("Arial", 28),
    fg="white",
    bg=background
)
hum_unit.pack()

status_label = tk.Label(
    frame,
    text="Status: --",
    font=("Arial", 22),
    fg="white",
    bg=background
)
status_label.pack(pady=10)

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
        temp_value,
        temp_unit,
        hum_value,
        hum_unit,
        status_label,
        clock
    )

    for widget in widgets:
        widget.configure(bg=color)


def update():
    temp, hum, sensor_status = read_sensor()

    if temp is not None:
        temp_value.config(text=f"{temp:.1f}")
        hum_value.config(text=f"{hum:.1f}")
        status_label.config(text=f"Status: {sensor_status}")

        if temp <= 20:
            set_color("#3498db")  # Blue - cool
        elif temp <= 25:
            set_color("#2ecc71")  # Green - comfortable
        elif temp <= 30:
            set_color("#f1c40f")  # Yellow - warm
        else:
            set_color("#e74c3c")  # Red - hot
    else:
        temp_value.config(text="--")
        hum_value.config(text="--")
        status_label.config(text=f"Status: {sensor_status}")

    clock.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())

update()

try:
    root.mainloop()
finally:
    bridge.switch_supply_off(0)
