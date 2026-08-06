# -*- coding: utf-8 -*-
"""
SEN66 sensor reader via Sensirion SensorBridge.
Provides a reusable class for PM_Halla and Eagle measurement setups.
"""
import time
import logging
import struct
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
    SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection, CrcCalculator, SensirionI2cCommand

logger = logging.getLogger(__name__)

# SEN66 I2C address
SEN66_I2C_ADDRESS = 0x6B

# SEN66 I2C commands (firmware 4.x compatible, command 0x0300 for data read).
# The public sensirion-i2c-sen66 package uses command 0x0414 which is only
# supported on newer firmware. We use the proven 0x0300 that matches the
# internal driver used in balena-silkroad.
_CRC = CrcCalculator(8, 0x31, 0xFF, 0x00)


class _CmdStartMeasurement(SensirionI2cCommand):
    def __init__(self):
        super().__init__(command=0x0021, tx_data=None, rx_length=None,
                         read_delay=0, timeout=0, crc=_CRC, command_bytes=2)


class _CmdStopMeasurement(SensirionI2cCommand):
    def __init__(self):
        super().__init__(command=0x0104, tx_data=None, rx_length=None,
                         read_delay=0, timeout=0, crc=_CRC, command_bytes=2,
                         post_processing_time=0.6)


class _CmdGetDataReady(SensirionI2cCommand):
    def __init__(self):
        super().__init__(command=0x0202, tx_data=None, rx_length=3,
                         read_delay=0.02, timeout=0, crc=_CRC, command_bytes=2)

    def interpret_response(self, data):
        # Returns (padding, data_ready) – data_ready is True when bit 0 of second byte is set
        return bool(data[1] & 0x01)


class _CmdReadMeasuredValues(SensirionI2cCommand):
    """Read measured values using command 0x0300 (firmware 4.x compatible)."""
    def __init__(self):
        super().__init__(command=0x0300, tx_data=None, rx_length=27,
                         read_delay=0.02, timeout=0, crc=_CRC, command_bytes=2)

    def interpret_response(self, data):
        # 9 x uint16/int16 values (CRC already stripped by driver).
        # Format: PM1.0, PM2.5, PM4.0, PM10.0 (uint16, /10)
        #         humidity (int16, /100), temperature (int16, /200)
        #         voc_index (int16, /10), nox_index (int16, /10)
        #         co2 (uint16, raw ppm)
        values = struct.unpack('>HHHHhhhhH', data)
        return values


class _CmdDeviceReset(SensirionI2cCommand):
    def __init__(self):
        super().__init__(command=0xD304, tx_data=None, rx_length=None,
                         read_delay=0, timeout=0, crc=_CRC, command_bytes=2,
                         post_processing_time=1.2)


class _CmdGetProductType(SensirionI2cCommand):
    def __init__(self):
        super().__init__(command=0xD002, tx_data=None, rx_length=48,
                         read_delay=0.02, timeout=0, crc=_CRC, command_bytes=2)

    def interpret_response(self, data):
        return data.rstrip(b'\x00').decode('ascii')


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

        # Configure SensorBridge port for I2C.
        # 50 kHz instead of 100 kHz: the measurement-data read is a 27-byte
        # transaction, and at 100 kHz the bus returns all-0xFF on long reads
        # (checksum errors), likely due to cable capacitance / pull-up issues.
        bridge.set_i2c_frequency(self.sensorbridge_port, frequency=50e3)
        bridge.set_supply_voltage(self.sensorbridge_port, voltage=3.3)
        bridge.switch_supply_on(self.sensorbridge_port)

        # Give the SEN66 time to boot after power-up before talking to it.
        # Without this delay the first I2C transaction is NACKed and the
        # SensorBridge reports "device with address 0 returned error 41".
        time.sleep(1.0)

        # Create I2C proxy and connection (using old-style I2cConnection
        # which properly supports read_delay via the SensorBridge proxy).
        i2c_transceiver = SensorBridgeI2cProxy(bridge, port=self.sensorbridge_port)
        self._i2c_connection = I2cConnection(i2c_transceiver)
        self._bridge = bridge

        # The SEN66 can NACK the first transactions right after boot. Retry, and
        # if it keeps failing, power-cycle the port to unstick the sensor before
        # giving up.
        try:
            self._retry_i2c(self._exec_reset, "device_reset")
        except RuntimeError:
            logger.warning("Reset failed; power-cycling SEN66 port %s", self.sensorbridge_port)
            bridge.switch_supply_off(self.sensorbridge_port)
            time.sleep(1.0)
            bridge.switch_supply_on(self.sensorbridge_port)
            time.sleep(1.2)
            self._retry_i2c(self._exec_reset, "device_reset")

        time.sleep(1.2)

        logger.info("Connected to SEN66 via SensorBridge on %s", self.serial_port_path)

    def _exec(self, cmd):
        """Execute an I2C command on the SEN66."""
        return self._i2c_connection.execute(SEN66_I2C_ADDRESS, cmd)

    def _exec_reset(self):
        return self._exec(_CmdDeviceReset())

    def _retry_i2c(self, func, name, attempts=5, delay=0.5):
        """Call an I2C operation, retrying on transient NACKs."""
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except Exception as error:  # noqa: BLE001 - includes I2cNackError
                last_error = error
                logger.warning(
                    "SEN66 %s failed on port %s (attempt %d/%d): %s",
                    name, self.sensorbridge_port, attempt, attempts, error,
                )
                time.sleep(delay)
        raise RuntimeError(
            f"SEN66 {name} did not succeed after {attempts} attempts. "
            "Check that the sensor is connected to the correct SensorBridge "
            "port and that wiring/power are OK."
        ) from last_error

    def start_measurement(self):
        """Start continuous measurement on SEN66."""
        self._retry_i2c(lambda: self._exec(_CmdStartMeasurement()), "start_measurement")
        time.sleep(1.1)  # Wait for first measurement
        logger.info("SEN66 measurement started")

    def _wait_for_data_ready(self, timeout=5.0, poll_interval=0.1):
        """Poll the SEN66 data-ready flag until new measurement data is available.

        Reading measured values before data is ready returns all-0xFF bytes,
        which the driver reports as a CRC/checksum error. Polling avoids that.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data_ready = self._retry_i2c(
                lambda: self._exec(_CmdGetDataReady()), "get_data_ready"
            )
            if data_ready:
                return
            time.sleep(poll_interval)
        raise RuntimeError("Timed out waiting for SEN66 data to become ready")

    def read_data(self):
        """
        Read all measured values from SEN66.

        Returns:
            dict with keys: pm1p0, pm2p5, pm4p0, pm10p0, humidity, temperature,
                           voc_index, nox_index, co2
        """
        self._wait_for_data_ready()
        values = self._retry_i2c(
            lambda: self._exec(_CmdReadMeasuredValues()), "read_measured_values")
        (pm1p0_raw, pm2p5_raw, pm4p0_raw, pm10p0_raw,
         humidity_raw, temperature_raw, voc_raw, nox_raw, co2_raw) = values
        return {
            "pm1p0": pm1p0_raw / 10.0,
            "pm2p5": pm2p5_raw / 10.0,
            "pm4p0": pm4p0_raw / 10.0,
            "pm10p0": pm10p0_raw / 10.0,
            "humidity": humidity_raw / 100.0,
            "temperature": temperature_raw / 200.0,
            "voc_index": voc_raw / 10.0,
            "nox_index": nox_raw / 10.0,
            "co2": co2_raw,
        }

    def stop_measurement(self):
        """Stop continuous measurement."""
        if self._i2c_connection:
            self._exec(_CmdStopMeasurement())
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
