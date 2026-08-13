import math
import tkinter as tk
import time
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
    SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_sht.sht4x import Sht4xI2cDevice

# --------------------------
# SENSORBRIDGE
# --------------------------

SERIAL_PORTS = ['/dev/ttyUSB0', '/dev/ttyUSB1']
BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
BRIDGE_PORT = SensorBridgePort.ONE


def find_bridge():
    for port in SERIAL_PORTS:
        try:
            serial_port = ShdlcSerialPort(port, BAUDRATE)
            bridge = SensorBridgeShdlcDevice(
                ShdlcConnection(serial_port), slave_address=0
            )
            print(f"SensorBridge found on {port}")
            return bridge
        except Exception:
            continue
    return None


bridge = find_bridge()
if bridge is None:
    print("ERROR: No SensorBridge found.")
    exit(1)

bridge.set_i2c_frequency(BRIDGE_PORT, I2C_FREQ)
bridge.set_supply_voltage(BRIDGE_PORT, SUPPLY_V)
bridge.switch_supply_on(BRIDGE_PORT)
time.sleep(0.5)

i2c_proxy = SensorBridgeI2cProxy(bridge, port=BRIDGE_PORT)
sensor = Sht4xI2cDevice(I2cConnection(i2c_proxy))

# --------------------------
# SENSOR
# --------------------------


def calc_dewpoint(temp_c, rh):
    """Magnus formula for dewpoint (TWS)."""
    a = 17.625
    b = 243.04
    alpha = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    return (b * alpha) / (a - alpha)


def read_sensor():
    try:
        temp, hum = sensor.single_shot_measurement()
        t = float(str(temp).split()[0])
        h = float(str(hum).split()[0])
        tws = calc_dewpoint(t, h)
        return t, h, tws, "Normal"
    except Exception as e:
        print(e)
        return None, None, None, "Error"


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
    text="SAAF4-ITHI",
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

tws_label = tk.Label(
    frame,
    text="TWS (Windshield)",
    font=("Arial", 24, "bold"),
    fg="white",
    bg=background
)
tws_label.pack(pady=(20, 0))

tws_value = tk.Label(
    frame,
    text="--",
    font=("Arial", 60, "bold"),
    fg="white",
    bg=background
)
tws_value.pack()

tws_unit = tk.Label(
    frame,
    text="°C (dewpoint)",
    font=("Arial", 22),
    fg="white",
    bg=background
)
tws_unit.pack()

status_label = tk.Label(
    frame,
    text="Status: --",
    font=("Arial", 22),
    fg="white",
    bg=background
)
status_label.pack(pady=10)


def set_color(color):
    root.configure(bg=color)
    frame.configure(bg=color)

    widgets = (
        title,
        temp_value,
        temp_unit,
        hum_value,
        hum_unit,
        tws_label,
        tws_value,
        tws_unit,
        status_label
    )

    for widget in widgets:
        widget.configure(bg=color)


def update():
    temp, hum, tws, sensor_status = read_sensor()

    if temp is not None:
        temp_value.config(text=f"{temp:.1f}")
        hum_value.config(text=f"{hum:.1f}")
        tws_value.config(text=f"{tws:.1f}")
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
        tws_value.config(text="--")
        status_label.config(text=f"Status: {sensor_status}")

    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())

update()

try:
    root.mainloop()
finally:
    bridge.switch_supply_off(BRIDGE_PORT)
