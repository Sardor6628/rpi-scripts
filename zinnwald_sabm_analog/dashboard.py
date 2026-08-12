# -*- coding: utf-8 -*-
"""
Rich terminal dashboard for Zinnwald SABM analog sensor.
Displays real-time voltage readings from MCC USB-1208FS-Plus DAQ.

Usage:
    python dashboard.py [--channel 0] [--label Zinnwald] [--interval 1]
"""
import argparse
import signal
import sys
import time
from collections import deque
from datetime import datetime

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from zinnwald_reader import ZinnwaldSensorDAQ
from uldaq import AiInputMode, Range

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# H2 concentration thresholds for status coloring (ppm).
# Baseline clean air is < 200 ppm; hydrogen LEL is ~4 vol% = 40000 ppm.
H2_THRESHOLDS = [
    (2000, "green"),        # < 0.2 vol% : normal
    (10000, "yellow"),      # < 1 vol%   : elevated
    (40000, "red"),         # < 4 vol%   : high (approaching LEL)
    (float("inf"), "bold red"),  # >= LEL
]


def get_color(value, thresholds):
    for limit, color in thresholds:
        if value < limit:
            return color
    return "white"


def build_dashboard(data, label, history, uptime_start):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=2),
        Layout(name="right", ratio=1),
    )

    # Header
    uptime = str(datetime.now() - uptime_start).split(".")[0]
    header_text = Text(
        f"  Zinnwald SABM (H₂) - {label}  |  Uptime: {uptime}  |  {datetime.now():%Y-%m-%d %H:%M:%S}",
        style="bold white on blue",
    )
    layout["header"].update(Panel(header_text, style="blue"))

    # Main sensor table
    table = Table(title="Current Readings", expand=True)
    table.add_column("Parameter", style="cyan", width=20)
    table.add_column("Value", justify="right", width=12)
    table.add_column("Unit", width=10)
    table.add_column("Status", width=10)

    if data:
        h2_color = get_color(data["h2_ppm"], H2_THRESHOLDS)
        status_color = "green" if data["status"] == "OK" else "yellow"

        table.add_row("Channel", str(data["channel"]), "", "")
        table.add_row("Voltage", f"{data['voltage']:.4f}", "V", "")
        table.add_row("", "", "", "")
        table.add_row("H₂", f"[{h2_color}]{data['h2_ppm']:.1f}[/]", "ppm",
                      f"[{h2_color}]●[/]")
        table.add_row("H₂", f"[{h2_color}]{data['h2_vol_percent']:.3f}[/]", "vol%", "")
        table.add_row("", "", "", "")
        table.add_row("Sensor Status", f"[{status_color}]{data['status']}[/]", "", "")
    else:
        table.add_row("Waiting for data...", "", "", "")

    layout["left"].update(Panel(table))

    # History panel (last 10 readings)
    history_table = Table(title="H₂ History", expand=True)
    history_table.add_column("Time", style="dim", width=8)
    history_table.add_column("H₂ [ppm]", justify="right", width=10)
    history_table.add_column("V", justify="right", width=8)

    for ts, h_data in list(history)[-10:]:
        h2_c = get_color(h_data["h2_ppm"], H2_THRESHOLDS)
        history_table.add_row(
            ts.strftime("%H:%M:%S"),
            f"[{h2_c}]{h_data['h2_ppm']:.1f}[/]",
            f"{h_data['voltage']:.3f}",
        )

    layout["right"].update(Panel(history_table))

    # Footer
    footer_text = Text(
        "  Press Ctrl+C to stop  |  ● Normal  ● Elevated  ● High (LEL)",
        style="dim",
    )
    layout["footer"].update(Panel(footer_text))

    return layout


RANGE_MAP = {
    "bip10v": Range.BIP10VOLTS,
    "bip5v": Range.BIP5VOLTS,
    "bip2v": Range.BIP2VOLTS,
    "bip1v": Range.BIP1VOLTS,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Zinnwald SABM sensor dashboard")
    parser.add_argument("--channel", type=int, default=0, help="Analog input channel (0-7)")
    parser.add_argument(
        "--mode",
        choices=["se", "diff"],
        default="se",
        help="Input mode: se=single-ended, diff=differential",
    )
    parser.add_argument(
        "--range",
        choices=["bip10v", "bip5v", "bip2v", "bip1v"],
        default="bip10v",
        help="Voltage range",
    )
    parser.add_argument("--label", default="Zinnwald", help="Measurement label")
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    console = Console()

    input_mode = AiInputMode.SINGLE_ENDED if args.mode == "se" else AiInputMode.DIFFERENTIAL
    voltage_range = RANGE_MAP[args.range]

    history = deque(maxlen=50)
    uptime_start = datetime.now()

    with ZinnwaldSensorDAQ(
        channel=args.channel,
        input_mode=input_mode,
        voltage_range=voltage_range,
    ) as sensor:
        time.sleep(0.5)
        with Live(
            build_dashboard(None, args.label, history, uptime_start),
            refresh_per_second=2,
            console=console,
        ) as live:
            while running:
                try:
                    data = sensor.read_data()
                    history.append((datetime.now(), data))
                    live.update(build_dashboard(data, args.label, history, uptime_start))
                    time.sleep(args.interval)
                except Exception as e:
                    console.print(f"[red]Read error: {e}[/red]")
                    time.sleep(1)

    console.print("\n[yellow]Measurement stopped.[/yellow]")


if __name__ == "__main__":
    main()
