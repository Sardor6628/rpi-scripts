import tkinter as tk
import time
from glob import glob
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

BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
BRIDGE_PORT = SensorBridgePort.ONE


def candidate_ports():
    # The SensorBridge normally enumerates as ttyUSB* (FTDI), but scan ttyACM*
    # too so a differently-enumerated bridge is still found.
    return sorted(glob('/dev/ttyUSB*') + glob('/dev/ttyACM*'))


def find_bridge():
    ports = candidate_ports()
    if not ports:
        print("No /dev/ttyUSB* or /dev/ttyACM* devices present.")
        print("Check the USB cable and run: lsusb; dmesg | tail -30")
        return None, None

    for port in ports:
        serial_port = None
        try:
            serial_port = ShdlcSerialPort(port, BAUDRATE)
            bridge = SensorBridgeShdlcDevice(
                ShdlcConnection(serial_port), slave_address=0
            )
            # Opening the serial port succeeds for any USB device, so query the
            # firmware version to confirm this really is a SensorBridge.
            bridge.get_version()
            print(f"SensorBridge found on {port}")
            return bridge, serial_port
        except Exception as exc:
            print(f"  {port}: {exc}")
            if serial_port is not None:
                try:
                    serial_port.close()
                except Exception:
                    pass
            continue
    return None, None


bridge, serial_port = find_bridge()
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


def read_sensor():
    try:
        temp, hum = sensor.single_shot_measurement()
        return temp.degrees_celsius, hum.percent_rh, "Normal"
    except Exception as e:
        print(e)
        return None, None, "Error"


# --------------------------
# THEME
# --------------------------

# (upper temperature bound, background, card background, caption)
THEMES = [
    (20, "#2f80c4", "#2670ad", "COOL"),
    (25, "#27a35c", "#1f8c4e", "COMFORTABLE"),
    (30, "#d9a406", "#bf9005", "WARM"),
    (float("inf"), "#d64031", "#bb3527", "HOT"),
]
THEME_NA = ("#5d6d7e", "#516070", "NO DATA")


def theme_for(temp):
    if temp is None:
        return THEME_NA
    for limit, bg, card, caption in THEMES:
        if temp <= limit:
            return bg, card, caption
    return THEME_NA


# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title("SAAF3-ITI")
root.attributes("-fullscreen", True)
root.config(cursor="none")

# Scale every font to the actual panel size so the layout fills the screen.
SCALE = max(0.6, min(root.winfo_screenwidth() / 1280.0, 2.0))


def pt(size):
    return max(8, int(size * SCALE))


BG, CARD, _ = THEME_NA
root.configure(bg=BG)

container = tk.Frame(root, bg=BG)
container.place(relx=0.5, rely=0.5, anchor="center")

title_lbl = tk.Label(
    container,
    text="SAAF3-ITI",
    font=("DejaVu Sans", pt(34), "bold"),
    fg="white",
    bg=BG
)
title_lbl.grid(row=0, column=0, columnspan=2, pady=(0, pt(30)))


def make_card(label_text, unit_text, col):
    card = tk.Frame(container, bg=CARD, padx=pt(46), pady=pt(26))
    card.grid(row=2, column=col, padx=pt(18))
    caption = tk.Label(
        card,
        text=label_text,
        font=("DejaVu Sans", pt(18), "bold"),
        fg="#e4ecf3",
        bg=CARD
    )
    caption.pack()
    value = tk.Label(
        card,
        text="--",
        font=("DejaVu Sans", pt(96), "bold"),
        fg="white",
        bg=CARD
    )
    value.pack()
    unit = tk.Label(
        card,
        text=unit_text,
        font=("DejaVu Sans", pt(22)),
        fg="#e4ecf3",
        bg=CARD
    )
    unit.pack()
    return card, caption, value, unit


temp_card, temp_caption, temp_value, temp_unit = make_card(
    "TEMPERATURE", "°C", 0)
hum_card, hum_caption, hum_value, hum_unit = make_card(
    "HUMIDITY", "% RH", 1)

state_lbl = tk.Label(
    container,
    text="--",
    font=("DejaVu Sans", pt(40), "bold"),
    fg="white",
    bg=BG
)
state_lbl.grid(row=3, column=0, columnspan=2, pady=(pt(30), 0))

status_lbl = tk.Label(
    container,
    text="Status: --",
    font=("DejaVu Sans", pt(16)),
    fg="#e4ecf3",
    bg=BG
)
status_lbl.grid(row=4, column=0, columnspan=2, pady=(pt(10), 0))

PAGE_WIDGETS = (container, title_lbl, state_lbl, status_lbl)
CARD_WIDGETS = (
    temp_card, temp_caption, temp_value, temp_unit,
    hum_card, hum_caption, hum_value, hum_unit,
)


def apply_theme(bg, card):
    root.configure(bg=bg)
    for widget in PAGE_WIDGETS:
        widget.configure(bg=bg)
    for widget in CARD_WIDGETS:
        widget.configure(bg=card)


def update():
    temp, hum, sensor_status = read_sensor()
    bg, card, caption = theme_for(temp)

    if temp is not None:
        temp_value.config(text=f"{temp:.1f}")
        hum_value.config(text=f"{hum:.1f}")
    else:
        temp_value.config(text="--")
        hum_value.config(text="--")

    state_lbl.config(text=caption)
    status_lbl.config(text=f"Status: {sensor_status}")
    apply_theme(bg, card)

    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())

update()

try:
    root.mainloop()
finally:
    try:
        bridge.switch_supply_off(BRIDGE_PORT)
    finally:
        serial_port.close()
