#!/usr/bin/env python3

import time
from uldaq import get_daq_device_inventory, DaqDevice, InterfaceType, AiInputMode, Range, AInFlag

devices = get_daq_device_inventory(InterfaceType.ANY)

if not devices:
    raise Exception("No USB-1208FS-PLUS found")

daq_device = DaqDevice(devices[0])
daq_device.connect()

ai_device = daq_device.get_ai_device()

channel = 0       # AI0
input_mode = AiInputMode.SINGLE_ENDED
ai_range = Range.BIP10VOLTS

print("Reading Zinnwald analog output...")

try:
    while True:
        voltage = ai_device.a_in(channel, input_mode, ai_range, AInFlag.DEFAULT)

        print(f"Voltage: {voltage:.3f} V")

        time.sleep(1)

except KeyboardInterrupt:
    pass

finally:
    daq_device.disconnect()
    daq_device.release()