# -*- coding: utf-8 -*-
"""
SEN66 sensor reader via Sensirion SensorBridge.
Provides a reusable class for PM_Halla and Eagle measurement setups.
"""
import time
import logging
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
    SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_sen6x import Sen6xI2cDevice

logger = logging.getLogger(__name__)

# SEN66 I2C address
SEN66_I2C_ADDRESS = 0x6B


class Sen66SensorBridge:
    """Reads SEN66 sensor data through a Sensirion SensorBridge."""

    def __init__(self, serial_port="/dev/ttyUSB0", sensorbridge_port=SensorBridgePort.ONE):
        """
        Args:
            serial_port: Serial port where the SensorBridge is connected.
            sensorbridge_port: Which SensorBridge port the SEN66 is on (ONE or TWO).
        """
        self.serial_port_path = serial_port
        self.sensorbridge_port = sensorbridge_port
        self._port = None
        self._bridge = None
        self._device = None

    def connect(self):
        """Open connection to SEN66 via SensorBridge."""
        self._port = ShdlcSerialPort(port=self.serial_port_path, baudrate=460800)
        bridge = SensorBridgeShdlcDevice(ShdlcConnection(self._port), slave_address=0)

        # Configure SensorBridge port for I2C
        bridge.set_i2c_frequency(self.sensorbridge_port, frequency=100e3)
        bridge.set_supply_voltage(self.sensorbridge_port, voltage=3.3)
        bridge.switch_supply_on(self.sensorbridge_port)

        # Create I2C proxy and SEN66 device
        i2c_transceiver = SensorBridgeI2cProxy(bridge, port=self.sensorbridge_port)
        self._device = Sen6xI2cDevice(I2cConnection(i2c_transceiver))
        self._bridge = bridge

        logger.info("Connected to SEN66 via SensorBridge on %s", self.serial_port_path)

    def start_measurement(self):
        """Start continuous measurement on SEN66."""
        self._device.start_measurement()
        time.sleep(1)  # Wait for first measurement
        logger.info("SEN66 measurement started")

    def read_data(self):
        """
        Read all measured values from SEN66.

        Returns:
            dict with keys: pm1p0, pm2p5, pm4p0, pm10p0, humidity, temperature,
                           voc_index, nox_index, co2
        """
        values = self._device.read_measured_values()
        return {
            "pm1p0": values.mass_concentration_1p0.physical,
            "pm2p5": values.mass_concentration_2p5.physical,
            "pm4p0": values.mass_concentration_4p0.physical,
            "pm10p0": values.mass_concentration_10p0.physical,
            "humidity": values.ambient_humidity.physical,
            "temperature": values.ambient_temperature.physical,
            "voc_index": values.voc_index.physical,
            "nox_index": values.nox_index.physical,
            "co2": values.co2.physical,
        }

    def stop_measurement(self):
        """Stop continuous measurement."""
        if self._device:
            self._device.stop_measurement()
            logger.info("SEN66 measurement stopped")

    def close(self):
        """Close all connections."""
        self.stop_measurement()
        if self._bridge:
            self._bridge.switch_supply_off(self.sensorbridge_port)
        if self._port:
            self._port.close()
        logger.info("SEN66 SensorBridge connection closed")

    def __enter__(self):
        self.connect()
        self.start_measurement()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
