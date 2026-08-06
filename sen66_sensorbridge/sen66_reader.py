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
from sensirion_i2c_driver import I2cConnection, CrcCalculator
from sensirion_driver_adapters.i2c_adapter.i2c_channel import I2cChannel
from sensirion_i2c_sen66.device import Sen66Device

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

        # Give the SEN66 time to boot after power-up before talking to it.
        # Without this delay the first I2C transaction is NACKed and the
        # SensorBridge reports "device with address 0 returned error 41".
        time.sleep(1.0)

        # Create I2C proxy and SEN66 device
        i2c_transceiver = SensorBridgeI2cProxy(bridge, port=self.sensorbridge_port)
        channel = I2cChannel(
            I2cConnection(i2c_transceiver),
            slave_address=SEN66_I2C_ADDRESS,
            crc=CrcCalculator(8, 0x31, 0xFF, 0x0),
        )
        self._device = Sen66Device(channel)
        self._bridge = bridge

        # The SEN66 may still NACK the first transactions right after boot.
        # Retry the reset a few times before giving up.
        last_error = None
        for attempt in range(1, 6):
            try:
                self._device.device_reset()
                break
            except Exception as error:  # noqa: BLE001 - includes I2cNackError
                last_error = error
                logger.warning(
                    "SEN66 not responding on port %s (attempt %d/5): %s",
                    self.sensorbridge_port, attempt, error,
                )
                time.sleep(0.5)
        else:
            raise RuntimeError(
                "SEN66 did not respond to reset after 5 attempts. "
                "Check that the sensor is connected to the correct SensorBridge "
                "port and that wiring/power are OK."
            ) from last_error

        time.sleep(1.2)

        logger.info("Connected to SEN66 via SensorBridge on %s", self.serial_port_path)

    def start_measurement(self):
        """Start continuous measurement on SEN66."""
        self._device.start_continuous_measurement()
        time.sleep(1.1)  # Wait for first measurement
        logger.info("SEN66 measurement started")

    def read_data(self):
        """
        Read all measured values from SEN66.

        Returns:
            dict with keys: pm1p0, pm2p5, pm4p0, pm10p0, humidity, temperature,
                           voc_index, nox_index, co2
        """
        (pm1p0, pm2p5, pm4p0, pm10p0, humidity,
         temperature, voc_index, nox_index, co2) = self._device.read_measured_values()
        return {
            "pm1p0": pm1p0,
            "pm2p5": pm2p5,
            "pm4p0": pm4p0,
            "pm10p0": pm10p0,
            "humidity": humidity,
            "temperature": temperature,
            "voc_index": voc_index,
            "nox_index": nox_index,
            "co2": co2,
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
