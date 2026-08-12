#!/usr/bin/env python3

import time
from uldaq import get_daq_device_inventory, DaqDevice, InterfaceType, AiInputMode, Range, AInFlag
from zinnwald_reader import voltage_to_h2_vol_percent, sensor_status

devices = get_daq_device_inventory(InterfaceType.ANY)

if not devices:
    raise Exception("No USB-1208FS-PLUS found")

daq_device = DaqDevice(devices[0])
daq_device.connect()

ai_device = daq_device.get_ai_device()

channel = 0       # AI0 -> Pos.3 ANA_1(TrA), wake-up channel (MOX), H2 sensor
input_mode = AiInputMode.SINGLE_ENDED
ai_range = Range.BIP10VOLTS

print("Reading Zinnwald SABM H2 sensor (Pos.3 wake-up channel)...")

try:
    while True:
        voltage = ai_device.a_in(channel, input_mode, ai_range, AInFlag.DEFAULT)

        h2_vol_percent = voltage_to_h2_vol_percent(voltage)
        status = sensor_status(voltage)
        print(
            f"{voltage:6.3f} V | H2: {h2_vol_percent * 10000:8.1f} ppm "
            f"({h2_vol_percent:6.3f} vol%) | {status}"
        )

        time.sleep(1)

except KeyboardInterrupt:
    pass

finally:
    daq_device.disconnect()
    daq_device.release()