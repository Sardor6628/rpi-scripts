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
sensor.start_measurement()
time.sleep(2)  # let the sensor stabilize


def read_sensor():
    try:
        return sensor.read_data()
    except Exception as e:
        print(e)
        return None


# --------------------------
# THEME (driven by PM2.5)
# --------------------------

# (upper PM2.5 bound, background, card background, caption)
THEMES = [
    (12, "#27a35c", "#1f8c4e", "GOOD"),
    (35, "#d9a406", "#bf9005", "MODERATE"),
    (55, "#e07b16", "#c26a11", "UNHEALTHY"),
    (float("inf"), "#d64031", "#bb3527", "DANGER"),
]
THEME_NA = ("#5d6d7e", "#516070", "NO DATA")


def theme_for(pm25):
    if pm25 is None:
        return THEME_NA
    for limit, bg, card, caption in THEMES:
        if pm25 < limit:
            return bg, card, caption
    return THEME_NA


# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title(f"SEN66 - {args.label}")
root.attributes("-fullscreen", True)
root.config(cursor="none")

# Scale every font to the actual panel size so the layout fills the screen.
SCALE = max(0.5, min(root.winfo_screenwidth() / 1280.0,
                     root.winfo_screenheight() / 800.0, 2.0))


def pt(size):
    return max(8, int(size * SCALE))


BG, CARD, _ = THEME_NA
root.configure(bg=BG)

container = tk.Frame(root, bg=BG)
container.place(relx=0.5, rely=0.5, anchor="center")

title_lbl = tk.Label(
    container,
    text=args.label,
    font=("DejaVu Sans", pt(34), "bold"),
    fg="white",
    bg=BG,
)
title_lbl.grid(row=0, column=0, columnspan=3, pady=(0, pt(4)))

subtitle_lbl = tk.Label(
    container,
    text="SEN66 AIR QUALITY",
    font=("DejaVu Sans", pt(14)),
    fg="#e4ecf3",
    bg=BG,
)
subtitle_lbl.grid(row=1, column=0, columnspan=3, pady=(0, pt(26)))


def make_card(label_text, unit_text, row, col):
    card = tk.Frame(container, bg=CARD, padx=pt(28), pady=pt(18))
    card.grid(row=row, column=col, padx=pt(12), pady=pt(10), sticky="nsew")
    caption = tk.Label(
        card,
        text=label_text,
        font=("DejaVu Sans", pt(16), "bold"),
        fg="#e4ecf3",
        bg=CARD,
    )
    caption.pack()
    value = tk.Label(
        card,
        text="--",
        font=("DejaVu Sans", pt(58), "bold"),
        fg="white",
        bg=CARD,
    )
    value.pack()
    unit = tk.Label(
        card,
        text=unit_text,
        font=("DejaVu Sans", pt(16)),
        fg="#e4ecf3",
        bg=CARD,
    )
    unit.pack()
    return card, caption, value, unit


pm25_card, pm25_caption, pm25_value, pm25_unit = make_card("PM 2.5", "µg/m³", 2, 0)
co2_card,  co2_caption,  co2_value,  co2_unit  = make_card("CO₂", "ppm", 2, 1)
voc_card,  voc_caption,  voc_value,  voc_unit  = make_card("VOC", "index", 2, 2)
temp_card, temp_caption, temp_value, temp_unit = make_card("TEMPERATURE", "°C", 3, 0)
hum_card,  hum_caption,  hum_value,  hum_unit  = make_card("HUMIDITY", "% RH", 3, 1)
pm10_card, pm10_caption, pm10_value, pm10_unit = make_card("PM 10", "µg/m³", 3, 2)

state_lbl = tk.Label(
    container,
    text="--",
    font=("DejaVu Sans", pt(40), "bold"),
    fg="white",
    bg=BG,
)
state_lbl.grid(row=4, column=0, columnspan=3, pady=(pt(26), 0))

status_lbl = tk.Label(
    container,
    text="Status: --",
    font=("DejaVu Sans", pt(16)),
    fg="#e4ecf3",
    bg=BG,
)
status_lbl.grid(row=5, column=0, columnspan=3, pady=(pt(10), 0))

PAGE_WIDGETS = (container, title_lbl, subtitle_lbl, state_lbl, status_lbl)
CARD_WIDGETS = (
    pm25_card, pm25_caption, pm25_value, pm25_unit,
    co2_card,  co2_caption,  co2_value,  co2_unit,
    voc_card,  voc_caption,  voc_value,  voc_unit,
    temp_card, temp_caption, temp_value, temp_unit,
    hum_card,  hum_caption,  hum_value,  hum_unit,
    pm10_card, pm10_caption, pm10_value, pm10_unit,
)

VALUE_WIDGETS = (pm25_value, co2_value, voc_value, temp_value, hum_value, pm10_value)


def apply_theme(bg, card):
    root.configure(bg=bg)
    for widget in PAGE_WIDGETS:
        widget.configure(bg=bg)
    for widget in CARD_WIDGETS:
        widget.configure(bg=card)


def update():
    data = read_sensor()
    pm25 = data["pm2p5"] if data else None
    bg, card, caption = theme_for(pm25)

    if data:
        pm25_value.config(text=f"{data['pm2p5']:.1f}")
        co2_value.config(text=f"{data['co2']:.0f}")
        voc_value.config(text=f"{data['voc_index']:.0f}")
        temp_value.config(text=f"{data['temperature']:.1f}")
        hum_value.config(text=f"{data['humidity']:.1f}")
        pm10_value.config(text=f"{data['pm10p0']:.1f}")
        status_lbl.config(text="Status: Normal")
    else:
        for widget in VALUE_WIDGETS:
            widget.config(text="--")
        status_lbl.config(text="Status: No Data")

    state_lbl.config(text=caption)
    apply_theme(bg, card)

    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())
update()

try:
    root.mainloop()
finally:
    sensor.close()
