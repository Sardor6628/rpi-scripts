# -*- coding: utf-8 -*-
"""
SensorBridge I2C diagnostic scanner.

Scans both SensorBridge ports across the full 7-bit I2C address range and
reports which addresses acknowledge. Use this to figure out whether the SEN66
is wired/powered correctly and on which port/address it lives.

Usage:
    python scan_bridge.py [--port /dev/ttyUSB0] [--voltage 3.3]
"""
import argparse
import logging
import time

from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
)

logging.basicConfig(level=logging.ERROR, format="%(asctime)s [%(levelname)s] %(message)s")

# SEN66 (and SEN63C/SEN65/SEN68) default I2C address.
SEN66_I2C_ADDRESS = 0x6B


def scan_port(bridge, port, port_label, voltage):
    """Power a port and probe every 7-bit I2C address; return list that ACKed."""
    print(f"\n--- Scanning SensorBridge port {port_label} at {voltage} V ---")
    bridge.set_i2c_frequency(port, frequency=100e3)
    bridge.set_supply_voltage(port, voltage=voltage)
    bridge.switch_supply_on(port)
    time.sleep(1.0)  # let any attached sensor boot

    found = []
    for address in range(0x08, 0x78):  # skip reserved addresses
        try:
            # A zero-length read is enough to see if the address ACKs.
            bridge.transceive_i2c(
                port,
                address=address,
                tx_data=b"",
                rx_length=1,
                timeout_us=20000,
            )
            found.append(address)
            print(f"  0x{address:02X}  ACK")
        except Exception:
            # NACK / no device at this address -> ignore.
            pass

    bridge.switch_supply_off(port)

    if not found:
        print("  (no devices responded)")
    return found


def main():
    parser = argparse.ArgumentParser(description="Scan SensorBridge I2C ports for devices")
    parser.add_argument("--port", default="/dev/ttyUSB0", help="SensorBridge serial port")
    parser.add_argument("--voltage", type=float, default=3.3, help="Supply voltage for the sensor")
    args = parser.parse_args()

    with ShdlcSerialPort(port=args.port, baudrate=460800) as shdlc_port:
        bridge = SensorBridgeShdlcDevice(ShdlcConnection(shdlc_port), slave_address=0)

        version = bridge.get_version()
        serial = bridge.get_serial_number()
        print(f"SensorBridge connected on {args.port}")
        print(f"  Firmware: {version}")
        print(f"  Serial:   {serial}")

        results = {}
        for port, label in ((SensorBridgePort.ONE, 1), (SensorBridgePort.TWO, 2)):
            results[label] = scan_port(bridge, port, label, args.voltage)

    print("\n=== Summary ===")
    any_found = False
    for label, addresses in results.items():
        if addresses:
            any_found = True
            addr_str = ", ".join(f"0x{a:02X}" for a in addresses)
            print(f"  Port {label}: {addr_str}")
            if SEN66_I2C_ADDRESS in addresses:
                print(f"    -> SEN66 found at 0x{SEN66_I2C_ADDRESS:02X}. Use --bridge-port {label}.")
        else:
            print(f"  Port {label}: nothing responded")

    if not any_found:
        print(
            "\nNo I2C devices responded on either port. This points to a hardware\n"
            "problem, not software: check the cable/connector orientation, that the\n"
            "sensor is fully seated, and that the correct supply voltage reaches it."
        )


if __name__ == "__main__":
    main()
