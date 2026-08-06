# -*- coding: utf-8 -*-
"""Quick SEN66 health check: reads identity registers (no measurement needed)."""
import time
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort, SensorBridgeShdlcDevice, SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection, CrcCalculator
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_sen66.device import Sen66Device

SEN66_I2C_ADDRESS = 0x6B

with ShdlcSerialPort(port="/dev/ttyUSB0", baudrate=460800) as port:
    bridge = SensorBridgeShdlcDevice(ShdlcConnection(port), slave_address=0)
    bridge.set_i2c_frequency(SensorBridgePort.ONE, frequency=100e3)
    bridge.set_supply_voltage(SensorBridgePort.ONE, voltage=3.3)
    bridge.switch_supply_on(SensorBridgePort.ONE)
    time.sleep(1.0)

    i2c = SensorBridgeI2cProxy(bridge, port=SensorBridgePort.ONE)
    channel = I2cChannel(
        I2cConnection(i2c),
        slave_address=SEN66_I2C_ADDRESS,
        crc=CrcCalculator(8, 0x31, 0xFF, 0x0),
    )
    dev = Sen66Device(channel)

    print("--- SEN66 identity ---")
    try:
        print(f"  Product type: {dev.get_product_type()}")
    except Exception as e:
        print(f"  Product type FAILED: {e}")
    try:
        print(f"  Product name: {dev.get_product_name()}")
    except Exception as e:
        print(f"  Product name FAILED: {e}")
    try:
        print(f"  Serial number: {dev.get_serial_number()}")
    except Exception as e:
        print(f"  Serial number FAILED: {e}")
    try:
        fw_major, fw_minor = dev.get_version()
        print(f"  Firmware: {fw_major}.{fw_minor}")
    except Exception as e:
        print(f"  Firmware FAILED: {e}")

    print("\n--- Start measurement + data ready test ---")
    try:
        dev.device_reset()
        time.sleep(1.2)
        dev.start_continuous_measurement()
        print("  Measurement started, waiting for data...")
        for i in range(30):  # up to 3 seconds
            time.sleep(0.1)
            try:
                _pad, ready = dev.get_data_ready()
                if ready:
                    print(f"  Data ready after {(i+1)*0.1:.1f}s")
                    vals = dev.read_measured_values_as_integers()
                    print(f"  Raw integers: {vals}")
                    break
            except Exception as e:
                print(f"  get_data_ready attempt {i+1}: {e}")
        else:
            print("  Data never became ready in 3 seconds")
        dev.stop_measurement()
    except Exception as e:
        print(f"  Measurement test FAILED: {e}")

    bridge.switch_supply_off(SensorBridgePort.ONE)
    print("\nDone.")
