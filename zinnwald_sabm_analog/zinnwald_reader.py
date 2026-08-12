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


# --- Pos. 3 = pin ANA_1(TrA): Wake-up channel (MOX sensor), target gas H2 ---
# Analog output voltage vs. H2 concentration (datasheet 2F0_907_637, Table 1):
#   0.5 V -> < 200 ppm H2 (clean-air baseline)
#   2.5 V -> 2 vol%  H2
#   4.5 V -> >= 12 vol% H2
# The response is non-linear, so we interpolate piecewise between these points.
#
# The lower measurement limit is ~0.519..0.59 V (Table 4). Below it the sensor
# cannot resolve H2, so readings there are just clean-air baseline + ADC noise.
# We anchor "0" at the typical lower measurement limit (0.59 V) and clamp below
# it to 0, which avoids amplifying 12-bit ADC quantization noise into tens of ppm.
LOWER_MEAS_LIMIT_V = 0.59
H2_CURVE = [(LOWER_MEAS_LIMIT_V, 0.0), (2.5, 2.0), (4.5, 12.0)]  # (volts, vol% H2)


def voltage_to_h2_vol_percent(voltage):
    """Convert Pos.3 wake-up-channel output voltage to H2 concentration [vol%]."""
    if voltage <= H2_CURVE[0][0]:
        return 0.0
    if voltage >= H2_CURVE[-1][0]:
        # Extrapolate along the last segment (>= 12 vol%)
        (v0, c0), (v1, c1) = H2_CURVE[-2], H2_CURVE[-1]
        return c1 + (voltage - v1) * (c1 - c0) / (v1 - v0)
    for (v0, c0), (v1, c1) in zip(H2_CURVE, H2_CURVE[1:]):
        if v0 <= voltage <= v1:
            return c0 + (voltage - v0) * (c1 - c0) / (v1 - v0)
    return 0.0


def sensor_status(voltage):
    """Human-readable status for the wake-up channel output voltage.

    Based on datasheet section 1.3 (error signaling) and Table 4 (voltage levels):
      < 0.25 V         fault / sensor disconnected
      0.25 .. 0.45 V   lower error band (0.35 V during wake-up)
      0.45 .. 0.59 V   clean air (below the lower measurement limit)
      0.59 .. 4.5 V    valid measurement
      > 4.5 V          over-range (H2 above upper measurement limit)
    """
    if voltage < 0.25:
        return "FAULT (below error band / disconnected)"
    if voltage <= 0.45:
        return "ERROR / WAKE-UP"
    if voltage < LOWER_MEAS_LIMIT_V:
        return "clean air (below detection limit)"
    if voltage <= 4.5:
        return "OK"
    return "OVER-RANGE (H2 above upper limit)"


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
        Read analog voltage from the Zinnwald sensor and derive H2 concentration.

        Returns:
            dict with keys: voltage, channel, h2_vol_percent, h2_ppm, status
        """
        voltage = self._ai_device.a_in(
            self.channel, self.input_mode, self.voltage_range, AInFlag.DEFAULT
        )
        h2_vol_percent = voltage_to_h2_vol_percent(voltage)
        return {
            "voltage": voltage,
            "channel": self.channel,
            "h2_vol_percent": h2_vol_percent,
            "h2_ppm": h2_vol_percent * 10000.0,
            "status": sensor_status(voltage),
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
