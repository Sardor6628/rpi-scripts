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

# Voltage thresholds for display coloring (adjust for your sensor's expected range)
VOLTAGE_THRESHOLDS = [
    (1.0, "green"),
    (3.0, "yellow"),
    (7.0, "red"),
    (float("inf"), "bold red"),
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

    # Header
    uptime = datetime.now() - uptime_start
    hours, remainder = divmod(int(uptime.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    header_text = Text(
        f"  Zinnwald SABM - {label}  |  Uptime: {hours:02d}:{minutes:02d}:{seconds:02d}  |  "
        f"{datetime.now():%Y-%m-%d %H:%M:%S}",
        style="bold white on blue",
    )
    layout["header"].update(Panel(header_text, style="blue"))

    # Body: left = current reading, right = history
    layout["body"].split_row(
        Layout(name="current", ratio=1),
        Layout(name="history", ratio=2),
    )

    # Current reading table
    table = Table(title="Current Reading", expand=True)
    table.add_column("Parameter", style="cyan", width=14)
    table.add_column("Value", justify="right", width=14)
    table.add_column("Unit", width=6)

    if data:
        v_color = get_color(abs(data["voltage"]), VOLTAGE_THRESHOLDS)
        table.add_row("Channel", str(data["channel"]), "")
        table.add_row("Voltage", f"[{v_color}]{data['voltage']:.6f}[/]", "V")
    else:
        table.add_row("Channel", "—", "")
        table.add_row("Voltage", "—", "V")

    layout["current"].update(Panel(table))

    # History table
    hist_table = Table(title=f"Last {len(history)} Readings", expand=True)
    hist_table.add_column("Time", style="dim", width=10)
    hist_table.add_column("Voltage [V]", justify="right", width=14)

    for ts, h_data in list(history)[-20:]:
        v_color = get_color(abs(h_data["voltage"]), VOLTAGE_THRESHOLDS)
        hist_table.add_row(
            f"{ts:%H:%M:%S}",
            f"[{v_color}]{h_data['voltage']:.6f}[/]",
        )

    layout["history"].update(Panel(hist_table))

    # Footer
    layout["footer"].update(
        Panel(Text("  Press Ctrl+C to stop", style="dim"), style="dim")
    )

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
