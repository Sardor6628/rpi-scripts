# -*- coding: utf-8 -*-
"""
Zinnwald SABM analog sensor reader via MCC USB-1208FS-Plus DAQ.
Provides a reusable class for the Sensor Wall measurement system.
"""
import time
import logging
from uldaq import (
    get_daq_device_inventory,
    DaqDevice,
    InterfaceType,
    AiInputMode,
    Range,
    AInFlag,
)

logger = logging.getLogger(__name__)


class ZinnwaldSensorDAQ:
    """Reads Zinnwald SABM analog sensor data through MCC USB-1208FS-Plus."""

    def __init__(self, channel=0, input_mode=AiInputMode.SINGLE_ENDED,
                 voltage_range=Range.BIP10VOLTS, device_index=0):
        """
        Args:
            channel: Analog input channel number (0-7 single-ended, 0-3 differential).
            input_mode: AiInputMode.SINGLE_ENDED or AiInputMode.DIFFERENTIAL.
            voltage_range: Voltage range for the measurement (e.g. Range.BIP10VOLTS).
            device_index: Index of the DAQ device if multiple are connected.
        """
        self.channel = channel
        self.input_mode = input_mode
        self.voltage_range = voltage_range
        self.device_index = device_index
        self._daq_device = None
        self._ai_device = None

    def connect(self):
        """Open connection to MCC USB-1208FS-Plus DAQ."""
        devices = get_daq_device_inventory(InterfaceType.USB)
        if not devices:
            raise RuntimeError("No MCC DAQ devices found on USB.")
        if self.device_index >= len(devices):
            raise RuntimeError(
                f"DAQ device index {self.device_index} out of range "
                f"({len(devices)} device(s) found)."
            )

        self._daq_device = DaqDevice(devices[self.device_index])
        self._daq_device.connect()
        self._ai_device = self._daq_device.get_ai_device()

        descriptor = devices[self.device_index]
        logger.info(
            "Connected to %s (serial: %s) on channel %d",
            descriptor.product_name,
            descriptor.unique_id,
            self.channel,
        )

    def read_data(self):
        """
        Read analog voltage from the Zinnwald sensor.

        Returns:
            dict with keys: voltage, channel
        """
        voltage = self._ai_device.a_in(
            self.channel, self.input_mode, self.voltage_range, AInFlag.DEFAULT
        )
        return {
            "voltage": voltage,
            "channel": self.channel,
        }

    def close(self):
        """Disconnect and release the DAQ device."""
        if self._daq_device:
            self._daq_device.disconnect()
            self._daq_device.release()
            logger.info("DAQ device disconnected")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
