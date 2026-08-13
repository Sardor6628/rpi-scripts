#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fullscreen dashboard for the SEN66 air-quality sensor (kumgang-style GUI).

Shows PM2.5, CO2, VOC, temperature, humidity and PM10 as large numbers in a grid
with a color-coded background driven by the PM2.5 air-quality level.

Usage:
    python dashboard.py [--port /dev/ttyUSB0] [--bridge-port 1] [--label PM_Halla]
"""
import argparse
import tkinter as tk
import time

from sen66_reader import Sen66SensorBridge
from sensirion_shdlc_sensorbridge import SensorBridgePort

# --------------------------
# ARGS / SENSOR
# --------------------------


def parse_args():
    parser = argparse.ArgumentParser(description="SEN66 fullscreen dashboard")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="SensorBridge serial port")
    parser.add_argument(
        "--bridge-port", type=int, choices=[1, 2], default=1,
        help="SensorBridge port number (1 or 2)",
    )
    parser.add_argument("--label", default="SEN66", help="Measurement label")
    return parser.parse_args()


args = parse_args()
bridge_port = SensorBridgePort.ONE if args.bridge_port == 1 else SensorBridgePort.TWO

sensor = Sen66SensorBridge(serial_port=args.port, sensorbridge_port=bridge_port)
sensor.connect()
time.sleep(2)  # let the sensor stabilize


def read_sensor():
    try:
        return sensor.read_data()
    except Exception as e:
        print(e)
        return None


# --------------------------
# Air-quality color / label (driven by PM2.5)
# --------------------------

PM25_THRESHOLDS = [
    (12, "#2ecc71", "GOOD"),
    (35, "#f1c40f", "MODERATE"),
    (55, "#e67e22", "UNHEALTHY"),
    (float("inf"), "#e74c3c", "DANGER"),
]
COLOR_NA = "#7f8c8d"


def pm_theme(pm25):
    if pm25 is None:
        return COLOR_NA, "NO DATA"
    for limit, color, label in PM25_THRESHOLDS:
        if pm25 < limit:
            return color, label
    return "#e74c3c", "DANGER"


# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title(f"SEN66 - {args.label}")
root.attributes("-fullscreen", True)

BG = "#2ecc71"
root.configure(bg=BG)

container = tk.Frame(root, bg=BG)
container.place(relx=0.5, rely=0.5, anchor="center")

title_lbl = tk.Label(
    container,
    text="SEN66",
    font=("Arial", 30, "bold"),
    fg="white", bg=BG,
)
title_lbl.grid(row=0, column=0, columnspan=3, pady=(0, 24))


def make_col(parent, label_text, unit_text, row, col):
    f = tk.Frame(parent, bg=BG, padx=30)
    f.grid(row=row, column=col, padx=20, pady=10)
    lbl = tk.Label(f, text=label_text, font=("Arial", 20, "bold"), fg="white", bg=BG)
    lbl.pack()
    val = tk.Label(f, text="--", font=("Arial", 72, "bold"), fg="white", bg=BG)
    val.pack()
    unt = tk.Label(f, text=unit_text, font=("Arial", 18), fg="white", bg=BG)
    unt.pack()
    return f, lbl, val, unt

# Row 1: PM2.5, CO2, VOC
pm25_f, pm25_t, pm25_v, pm25_u = make_col(container, "PM 2.5", "µg/m³", 1, 0)
co2_f,  co2_t,  co2_v,  co2_u  = make_col(container, "CO₂",    "ppm",   1, 1)
voc_f,  voc_t,  voc_v,  voc_u  = make_col(container, "VOC",    "index", 1, 2)

# Row 2: Temperature, Humidity, PM10
temp_f, temp_t, temp_v, temp_u = make_col(container, "Temperature", "°C",    2, 0)
hum_f,  hum_t,  hum_v,  hum_u  = make_col(container, "Humidity",    "%RH",   2, 1)
pm10_f, pm10_t, pm10_v, pm10_u = make_col(container, "PM 10",       "µg/m³", 2, 2)

quality_lbl = tk.Label(
    container,
    text="--",
    font=("Arial", 42, "bold"),
    fg="white", bg=BG,
)
quality_lbl.grid(row=3, column=0, columnspan=3, pady=14)

status_lbl = tk.Label(
    container,
    text="Status: --",
    font=("Arial", 20),
    fg="white", bg=BG,
)
status_lbl.grid(row=4, column=0, columnspan=3)

ALL_WIDGETS = [
    container, title_lbl, quality_lbl, status_lbl,
    pm25_f, pm25_t, pm25_v, pm25_u,
    co2_f,  co2_t,  co2_v,  co2_u,
    voc_f,  voc_t,  voc_v,  voc_u,
    temp_f, temp_t, temp_v, temp_u,
    hum_f,  hum_t,  hum_v,  hum_u,
    pm10_f, pm10_t, pm10_v, pm10_u,
]


def set_bg(color):
    root.configure(bg=color)
    for w in ALL_WIDGETS:
        w.configure(bg=color)


def update():
    data = read_sensor()
    pm25 = data["pm2p5"] if data else None
    color, label = pm_theme(pm25)

    set_bg(color)
    quality_lbl.config(text=label)

    if data:
        pm25_v.config(text=f"{data['pm2p5']:.1f}")
        co2_v.config(text=f"{data['co2']:.0f}")
        voc_v.config(text=f"{data['voc_index']:.0f}")
        temp_v.config(text=f"{data['temperature']:.1f}")
        hum_v.config(text=f"{data['humidity']:.1f}")
        pm10_v.config(text=f"{data['pm10p0']:.1f}")
        status_lbl.config(text="Status: Normal")
    else:
        for v in (pm25_v, co2_v, voc_v, temp_v, hum_v, pm10_v):
            v.config(text="--")
        status_lbl.config(text="Status: No Data")

    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())
update()

try:
    root.mainloop()
finally:
    sensor.close()
