# -*- coding: utf-8 -*-
"""
Live terminal dashboard for SEN66 sensor data.
Supports PM_Halla and Eagle measurement setups via SensorBridge.

Usage:
    python dashboard.py [--port /dev/ttyUSB0] [--label PM_Halla|Eagle] [--interval 1]
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

from sen66_reader import Sen66SensorBridge
from sensirion_shdlc_sensorbridge import SensorBridgePort

console = Console()
running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


# Air quality thresholds
PM25_THRESHOLDS = [(12, "green"), (35, "yellow"), (55, "red"), (float("inf"), "bold red")]
VOC_THRESHOLDS = [(100, "green"), (200, "yellow"), (300, "red"), (float("inf"), "bold red")]
CO2_THRESHOLDS = [(800, "green"), (1200, "yellow"), (2000, "red"), (float("inf"), "bold red")]


def get_color(value, thresholds):
    for limit, color in thresholds:
        if value < limit:
            return color
    return "white"


def build_dashboard(data, label, history, uptime_start):
    """Build the rich dashboard layout."""
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
    header_text = Text(f"  SEN66 Dashboard - {label}  |  Uptime: {uptime}", style="bold white on blue")
    layout["header"].update(Panel(header_text, style="blue"))

    # Main sensor table
    table = Table(title="Current Readings", expand=True)
    table.add_column("Parameter", style="cyan", width=20)
    table.add_column("Value", justify="right", width=12)
    table.add_column("Unit", width=10)
    table.add_column("Status", width=10)

    if data:
        pm25_color = get_color(data["pm2p5"], PM25_THRESHOLDS)
        voc_color = get_color(data["voc_index"], VOC_THRESHOLDS)
        co2_color = get_color(data["co2"], CO2_THRESHOLDS)

        table.add_row("PM 1.0", f"{data['pm1p0']:.1f}", "µg/m³", "")
        table.add_row("PM 2.5", f"[{pm25_color}]{data['pm2p5']:.1f}[/]", "µg/m³",
                      f"[{pm25_color}]●[/]")
        table.add_row("PM 4.0", f"{data['pm4p0']:.1f}", "µg/m³", "")
        table.add_row("PM 10", f"{data['pm10p0']:.1f}", "µg/m³", "")
        table.add_row("", "", "", "")
        table.add_row("Temperature", f"{data['temperature']:.1f}", "°C", "")
        table.add_row("Humidity", f"{data['humidity']:.1f}", "%RH", "")
        table.add_row("", "", "", "")
        table.add_row("VOC Index", f"[{voc_color}]{data['voc_index']:.0f}[/]", "",
                      f"[{voc_color}]●[/]")
        table.add_row("NOx Index", f"{data['nox_index']:.0f}", "", "")
        table.add_row("CO₂", f"[{co2_color}]{data['co2']:.0f}[/]", "ppm",
                      f"[{co2_color}]●[/]")
    else:
        table.add_row("Waiting for data...", "", "", "")

    layout["left"].update(Panel(table))

    # History panel (last 10 readings)
    history_table = Table(title="PM2.5 History", expand=True)
    history_table.add_column("Time", style="dim", width=8)
    history_table.add_column("PM2.5", justify="right", width=7)
    history_table.add_column("CO₂", justify="right", width=6)

    for ts, h_data in list(history)[-10:]:
        pm_color = get_color(h_data["pm2p5"], PM25_THRESHOLDS)
        co2_c = get_color(h_data["co2"], CO2_THRESHOLDS)
        history_table.add_row(
            ts.strftime("%H:%M:%S"),
            f"[{pm_color}]{h_data['pm2p5']:.1f}[/]",
            f"[{co2_c}]{h_data['co2']:.0f}[/]",
        )

    layout["right"].update(Panel(history_table))

    # Footer
    footer_text = Text("  Press Ctrl+C to stop  |  ● Good  ● Moderate  ● Poor", style="dim")
    layout["footer"].update(Panel(footer_text))

    return layout


def parse_args():
    parser = argparse.ArgumentParser(description="SEN66 live dashboard via SensorBridge")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="SensorBridge serial port")
    parser.add_argument(
        "--bridge-port",
        type=int,
        choices=[1, 2],
        default=1,
        help="SensorBridge port number (1 or 2)",
    )
    parser.add_argument(
        "--label",
        default="PM_Halla",
        choices=["PM_Halla", "Eagle"],
        help="Measurement label",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Refresh interval in seconds")
    return parser.parse_args()


def main():
    args = parse_args()
    bridge_port = SensorBridgePort.ONE if args.bridge_port == 1 else SensorBridgePort.TWO
    history = deque(maxlen=50)
    uptime_start = datetime.now()

    console.print(f"[bold]Connecting to SEN66 on {args.port}...[/bold]")

    with Sen66SensorBridge(serial_port=args.port, sensorbridge_port=bridge_port) as sensor:
        time.sleep(2)  # Wait for sensor to stabilize
        console.print("[green]Connected! Starting dashboard...[/green]")
        time.sleep(1)

        data = None
        with Live(build_dashboard(data, args.label, history, uptime_start),
                  refresh_per_second=2, console=console) as live:
            while running:
                try:
                    data = sensor.read_data()
                    history.append((datetime.now(), data))
                    live.update(build_dashboard(data, args.label, history, uptime_start))
                    time.sleep(args.interval)
                except Exception as e:
                    console.print(f"[red]Error: {e}[/red]")
                    time.sleep(1)

    console.print("[yellow]Dashboard stopped.[/yellow]")


if __name__ == "__main__":
    main()
