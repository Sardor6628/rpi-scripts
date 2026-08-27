#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live H2 trend chart for the Zinnwald SABM analog sensor.

Shows the last N minutes of H2 readings as a line chart. Default window is 3
minutes, and the duration can be increased from the command line.
"""
import argparse
import datetime as dt
import time
from collections import deque

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:
    raise SystemExit(
        "matplotlib is not installed. Install it with: pip install matplotlib\n"
        "Or reinstall the project environment with: pip install -r requirements.txt"
    ) from exc

from zinnwald_reader import ZinnwaldSensorDAQ
from uldaq import AiInputMode, Range

RANGE_MAP = {
    "bip10v": Range.BIP10VOLTS,
    "bip5v": Range.BIP5VOLTS,
    "bip2v": Range.BIP2VOLTS,
    "bip1v": Range.BIP1VOLTS,
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Plot the last N minutes of Zinnwald SABM H2 readings."
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=3.0,
        help="Window length in minutes to display (default: 3.0)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Sample interval in seconds (default: 1.0)",
    )
    parser.add_argument(
        "--channel",
        type=int,
        default=0,
        help="Analog input channel (default: 0)",
    )
    parser.add_argument(
        "--mode",
        choices=["se", "diff"],
        default="se",
        help="Input mode: se=single-ended, diff=differential",
    )
    parser.add_argument(
        "--range",
        choices=list(RANGE_MAP),
        default="bip10v",
        help="Voltage range",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_mode = AiInputMode.SINGLE_ENDED if args.mode == "se" else AiInputMode.DIFFERENTIAL

    sensor = ZinnwaldSensorDAQ(
        channel=args.channel,
        input_mode=input_mode,
        voltage_range=RANGE_MAP[args.range],
    )
    sensor.connect()

    window_seconds = max(60.0, args.duration * 60.0)
    max_points = max(10, int(window_seconds / max(args.interval, 0.5)))
    samples = deque(maxlen=max_points)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(11, 6))
    fig.canvas.manager.set_window_title("Zinnwald SABM H2 Trend")
    line, = ax.plot([], [], color="tab:green", linewidth=2, marker="o", markersize=3)
    ax.set_title(f"Zinnwald H2 trend (last {args.duration:.1f} min)")
    ax.set_xlabel("Time")
    ax.set_ylabel("H2 [ppm]")
    ax.grid(True, alpha=0.4)

    def draw():
        if not samples:
            ax.set_ylim(0, 1)
            ax.set_xlim(0, 1)
            fig.canvas.draw_idle()
            return

        timestamps = [ts for ts, _ in samples]
        values = [value for _, value in samples]

        times = [dt.datetime.fromtimestamp(ts) for ts in timestamps]
        line.set_xdata(times)
        line.set_ydata(values)

        ax.set_title(f"Zinnwald H2 trend (last {args.duration:.1f} min)")
        ax.set_xlabel("Time")
        ax.set_ylabel("H2 [ppm]")

        ymin = 0 if min(values) <= 0 else max(0.0, min(values) * 0.9)
        ymax = max(values) * 1.15 if max(values) > 0 else 100.0
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(min(times), max(times))
        fig.autofmt_xdate()
        fig.canvas.draw_idle()

    try:
        while True:
            data = sensor.read_data()
            samples.append((time.time(), float(data["h2_ppm"])))
            draw()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nStop requested. Closing plot.")
    finally:
        sensor.close()
        plt.close(fig)


if __name__ == "__main__":
    main()
