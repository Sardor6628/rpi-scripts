#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Live voltage trend chart for the Zinnwald SABM analog sensor.

Shows the last N minutes of the Pos.3 wake-up channel output voltage as a line
chart. Default window is 3 minutes, and the duration can be changed from the
command line.
"""
import argparse
import datetime as dt
import time
from collections import deque

try:
    import matplotlib
    matplotlib.use("TkAgg", force=True)
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
except ModuleNotFoundError as exc:
    raise SystemExit(
        "matplotlib is not installed. Install it with: pip install matplotlib\n"
        "Or reinstall the project environment with: pip install -r requirements.txt"
    ) from exc
except ImportError as exc:
    raise SystemExit(
        f"Cannot load the TkAgg GUI backend: {exc}\n"
        "Install the GUI dependencies with:\n"
        "  sudo apt-get install -y python3-tk\n"
        "  pip install --upgrade matplotlib pillow"
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
        description="Plot the last N minutes of Zinnwald SABM sensor voltage."
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
    parser.add_argument(
        "--ymax",
        type=float,
        default=3.0,
        help="Fixed upper limit of the voltage axis in volts (default: 3.0). "
             "The axis grows automatically if a reading exceeds it.",
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
    try:
        fig.canvas.manager.set_window_title("Zinnwald SABM Voltage Trend")
    except Exception:
        pass
    line, = ax.plot([], [], color="tab:green", linewidth=2, marker="o", markersize=3)
    ax.set_title(f"Zinnwald voltage trend (last {args.duration:.1f} min)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Signal [V]")
    ax.set_ylim(0, args.ymax)
    ax.grid(True, alpha=0.4)

    # The line starts empty, so matplotlib does not know the x data are dates.
    # Register the date unit explicitly, otherwise the axis renders raw floats.
    ax.xaxis_date()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    fig.autofmt_xdate()

    plt.ion()
    plt.show(block=False)

    def draw():
        now = dt.datetime.now()
        ax.set_xlim(now - dt.timedelta(seconds=window_seconds), now)

        if not samples:
            ax.set_ylim(0, args.ymax)
            fig.canvas.draw_idle()
            return

        times = [dt.datetime.fromtimestamp(ts) for ts, _ in samples]
        values = [value for _, value in samples]
        line.set_data(times, values)

        ymax = args.ymax if max(values) <= args.ymax else max(values) * 1.15
        ax.set_ylim(0, ymax)
        fig.canvas.draw_idle()

    try:
        while plt.fignum_exists(fig.number):
            data = sensor.read_data()
            samples.append((time.time(), float(data["voltage"])))
            draw()
            plt.pause(args.interval)
    except KeyboardInterrupt:
        print("\nStop requested. Closing plot.")
    finally:
        sensor.close()
        plt.close(fig)


if __name__ == "__main__":
    main()
