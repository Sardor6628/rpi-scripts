# -*- coding: utf-8 -*-
"""
Print Zinnwald SABM analog sensor data to console.
Reads analog voltage from MCC USB-1208FS-Plus DAQ.

Usage:
    python print_sensor_data.py [--channel 0] [--label Zinnwald] [--interval 1]
"""
import argparse
import logging
import signal
import sys
import time
from datetime import datetime

from zinnwald_reader import ZinnwaldSensorDAQ
from uldaq import AiInputMode, Range

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

running = True


def signal_handler(sig, frame):
    global running
    running = False


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def parse_args():
    parser = argparse.ArgumentParser(description="Print Zinnwald SABM analog sensor data")
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
    parser.add_argument("--csv", action="store_true", help="Output in CSV format")
    return parser.parse_args()


RANGE_MAP = {
    "bip10v": Range.BIP10VOLTS,
    "bip5v": Range.BIP5VOLTS,
    "bip2v": Range.BIP2VOLTS,
    "bip1v": Range.BIP1VOLTS,
}


def print_header(label, csv_mode):
    if csv_mode:
        print("timestamp,label,channel,voltage_V")
    else:
        print(f"\n{'='*50}")
        print(f"  Zinnwald SABM Measurement - {label}")
        print(f"{'='*50}")
        print(f"{'Timestamp':<22} {'Ch':>3} {'Voltage [V]':>12}")
        print(f"{'-'*50}")


def print_data(data, label, csv_mode):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if csv_mode:
        print(f"{ts},{label},{data['channel']},{data['voltage']:.6f}")
    else:
        print(f"{ts}  {data['channel']:3d} {data['voltage']:12.6f}")
    sys.stdout.flush()


def main():
    args = parse_args()

    input_mode = AiInputMode.SINGLE_ENDED if args.mode == "se" else AiInputMode.DIFFERENTIAL
    voltage_range = RANGE_MAP[args.range]

    logger.info(
        "Starting Zinnwald measurement [%s] on channel %d (%s, %s)",
        args.label, args.channel, args.mode, args.range,
    )

    with ZinnwaldSensorDAQ(
        channel=args.channel,
        input_mode=input_mode,
        voltage_range=voltage_range,
    ) as sensor:
        time.sleep(0.5)
        print_header(args.label, args.csv)

        while running:
            try:
                data = sensor.read_data()
                print_data(data, args.label, args.csv)
                time.sleep(args.interval)
            except Exception as e:
                logger.error("Read error: %s", e)
                time.sleep(1)

    logger.info("Measurement stopped")


if __name__ == "__main__":
    main()
