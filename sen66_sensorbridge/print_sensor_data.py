# -*- coding: utf-8 -*-
"""
Print SEN66 sensor data to console.
Supports PM_Halla and Eagle measurement setups via SensorBridge.

Usage:
    python print_sensor_data.py [--port /dev/ttyUSB0] [--label PM_Halla|Eagle] [--interval 1]
"""
import argparse
import logging
import signal
import sys
import time
from datetime import datetime

from sen66_reader import Sen66SensorBridge
from sensirion_shdlc_sensorbridge import SensorBridgePort

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
    parser = argparse.ArgumentParser(description="Print SEN66 sensor data via SensorBridge")
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
        default="SEN66",
        help="Measurement label",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Sampling interval in seconds")
    parser.add_argument("--csv", action="store_true", help="Output in CSV format")
    return parser.parse_args()


def print_header(label, csv_mode):
    if csv_mode:
        print("timestamp,label,pm1p0,pm2p5,pm4p0,pm10p0,humidity,temperature,voc_index,nox_index,co2")
    else:
        print(f"\n{'='*70}")
        print(f"  SEN66 Measurement - {label}")
        print(f"{'='*70}")
        print(f"{'Timestamp':<22} {'PM1.0':>7} {'PM2.5':>7} {'PM4.0':>7} {'PM10':>7} "
              f"{'RH%':>6} {'T°C':>6} {'VOC':>5} {'NOx':>5} {'CO2':>6}")
        print(f"{'-'*70}")


def print_data(data, label, csv_mode):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if csv_mode:
        print(f"{ts},{label},{data['pm1p0']:.1f},{data['pm2p5']:.1f},{data['pm4p0']:.1f},"
              f"{data['pm10p0']:.1f},{data['humidity']:.1f},{data['temperature']:.1f},"
              f"{data['voc_index']:.0f},{data['nox_index']:.0f},{data['co2']:.0f}")
    else:
        print(f"{ts}  {data['pm1p0']:7.1f} {data['pm2p5']:7.1f} {data['pm4p0']:7.1f} "
              f"{data['pm10p0']:7.1f} {data['humidity']:6.1f} {data['temperature']:6.1f} "
              f"{data['voc_index']:5.0f} {data['nox_index']:5.0f} {data['co2']:6.0f}")
    sys.stdout.flush()


def main():
    args = parse_args()
    bridge_port = SensorBridgePort.ONE if args.bridge_port == 1 else SensorBridgePort.TWO

    logger.info("Starting SEN66 measurement [%s] on %s (port %d)",
                args.label, args.port, args.bridge_port)

    with Sen66SensorBridge(serial_port=args.port, sensorbridge_port=bridge_port) as sensor:
        # Wait for sensor to stabilize
        time.sleep(2)
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
