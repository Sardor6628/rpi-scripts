#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fullscreen dashboard for the Zinnwald SABM analog H2 sensor (kumgang-style GUI).

Reads the Pos.3 wake-up channel (MOX) via MCC USB-1208FS-Plus DAQ and shows the
H2 concentration as large numbers with a color-coded background.

Usage:
    python dashboard.py [--channel 0] [--label Zinnwald] [--range bip10v]
"""
import argparse
import tkinter as tk
import time

from zinnwald_reader import ZinnwaldSensorDAQ
from uldaq import AiInputMode, Range

# --------------------------
# ARGS / SENSOR
# --------------------------

RANGE_MAP = {
    "bip10v": Range.BIP10VOLTS,
    "bip5v": Range.BIP5VOLTS,
    "bip2v": Range.BIP2VOLTS,
    "bip1v": Range.BIP1VOLTS,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Zinnwald SABM H2 fullscreen dashboard")
    parser.add_argument("--channel", type=int, default=0, help="Analog input channel (0-7)")
    parser.add_argument(
        "--mode", choices=["se", "diff"], default="se",
        help="Input mode: se=single-ended, diff=differential",
    )
    parser.add_argument(
        "--range", choices=list(RANGE_MAP), default="bip10v", help="Voltage range",
    )
    parser.add_argument("--label", default="Zinnwald", help="Measurement label")
    return parser.parse_args()


args = parse_args()
input_mode = AiInputMode.SINGLE_ENDED if args.mode == "se" else AiInputMode.DIFFERENTIAL

sensor = ZinnwaldSensorDAQ(
    channel=args.channel,
    input_mode=input_mode,
    voltage_range=RANGE_MAP[args.range],
)
sensor.connect()
time.sleep(0.5)


def read_sensor():
    try:
        data = sensor.read_data()
        return data, data["status"]
    except Exception as e:
        print(e)
        return None, "Error"


# --------------------------
# H2 color / label
# --------------------------

# H2 thresholds in ppm (baseline clean air < 200 ppm, hydrogen LEL ~4 vol% = 40000 ppm)
THRESHOLDS = [
    (2000, "#2ecc71", "NORMAL"),       # < 0.2 vol%
    (10000, "#f1c40f", "ELEVATED"),    # < 1 vol%
    (40000, "#e67e22", "HIGH"),        # < 4 vol% (approaching LEL)
    (float("inf"), "#e74c3c", "DANGER (LEL)"),
]
COLOR_NA = "#7f8c8d"


def h2_theme(ppm):
    for limit, color, label in THRESHOLDS:
        if ppm < limit:
            return color, label
    return "#e74c3c", "DANGER (LEL)"


# --------------------------
# GUI
# --------------------------

root = tk.Tk()
root.title("Zinnwald SABM - H2")
root.attributes("-fullscreen", True)

background = "#2ecc71"
root.configure(bg=background)

frame = tk.Frame(root, bg=background)
frame.place(relx=0.5, rely=0.5, anchor="center")

title = tk.Label(
    frame,
    text=f"Hydrogen (H₂) - {args.label}",
    font=("Arial", 34, "bold"),
    fg="white",
    bg=background,
)
title.pack()

h2_value = tk.Label(
    frame,
    text="--",
    font=("Arial", 130, "bold"),
    fg="white",
    bg=background,
)
h2_value.pack()

h2_unit = tk.Label(
    frame,
    text="ppm",
    font=("Arial", 28),
    fg="white",
    bg=background,
)
h2_unit.pack()

quality = tk.Label(
    frame,
    text="--",
    font=("Arial", 42, "bold"),
    fg="white",
    bg=background,
)
quality.pack(pady=10)

volpct_value = tk.Label(
    frame,
    text="--",
    font=("Arial", 40, "bold"),
    fg="white",
    bg=background,
)
volpct_value.pack(pady=(10, 0))

volpct_unit = tk.Label(
    frame,
    text="vol %",
    font=("Arial", 22),
    fg="white",
    bg=background,
)
volpct_unit.pack()

voltage_label = tk.Label(
    frame,
    text="Voltage: --",
    font=("Arial", 22),
    fg="white",
    bg=background,
)
voltage_label.pack(pady=(20, 0))

status_label = tk.Label(
    frame,
    text="Status: --",
    font=("Arial", 22),
    fg="white",
    bg=background,
)
status_label.pack(pady=4)

clock = tk.Label(
    frame,
    text="",
    font=("Arial", 18),
    fg="white",
    bg=background,
)
clock.pack(pady=10)


def set_color(color):
    root.configure(bg=color)
    frame.configure(bg=color)

    widgets = (
        title,
        h2_value,
        h2_unit,
        quality,
        volpct_value,
        volpct_unit,
        voltage_label,
        status_label,
        clock,
    )

    for widget in widgets:
        widget.configure(bg=color)


def update():
    data, sensor_status = read_sensor()

    if data is not None:
        h2_value.config(text=f"{data['h2_ppm']:.0f}")
        volpct_value.config(text=f"{data['h2_vol_percent']:.3f}")
        voltage_label.config(text=f"Voltage: {data['voltage']:.4f} V")
        status_label.config(text=f"Status: {sensor_status}")

        if sensor_status in ("FAULT (below error band / disconnected)",
                             "ERROR / WAKE-UP",
                             "OVER-RANGE (H2 above upper limit)"):
            color, label = COLOR_NA, sensor_status.upper()
        else:
            color, label = h2_theme(data["h2_ppm"])

        set_color(color)
        quality.config(text=label)
    else:
        h2_value.config(text="--")
        volpct_value.config(text="--")
        voltage_label.config(text="Voltage: --")
        status_label.config(text=f"Status: {sensor_status}")
        set_color(COLOR_NA)
        quality.config(text="NO DATA")

    clock.config(text=time.strftime("%H:%M:%S"))
    root.after(1000, update)


root.bind("<Escape>", lambda e: root.destroy())

update()

try:
    root.mainloop()
finally:
    sensor.close()
