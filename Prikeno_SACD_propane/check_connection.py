import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

FRAME_MASTER = "1D"  # SACD_Master_Frame
FRAME_SLAVE  = "1F"  # SACD_Sensor_Frame


def send(cmd, delay=0.06):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()


def set_active():
    # MeasureMode=1 (DrivingMode) @bit0, MasterPressure=50 (1000 mbar) @bit52,
    # everything in between left at Init so the sensor uses its own defaults.
    v = 1
    v |= 0xFF << 2      # Debounce1
    v |= 0xFF << 10     # Debounce2
    v |= 0xFF << 18     # MeasureRate
    v |= 0x3FF << 26    # ObservationTime
    v |= 0xFF << 36     # Threshold1
    v |= 0xFF << 44     # Threshold2
    v |= 50 << 52       # MasterPressure
    payload = v.to_bytes(8, "little").hex().upper()
    send(f"T{FRAME_MASTER}8{payload}")


def read_sensor_frame():
    rx = send(f"r{FRAME_SLAVE}", 0.15)
    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find(FRAME_SLAVE)
    if i < 0 or len(h) < i + 2 + 16:
        return None, rx
    return h[i + 2:i + 18], rx


print(send("V", 0.2))
send("S3")
send("O")

try:
    set_active()
    time.sleep(1)
    while True:
        data_hex, raw = read_sensor_frame()
        if data_hex:
            print(f"{datetime.now():%H:%M:%S} DATA id={FRAME_SLAVE} payload={data_hex} raw={raw}")
        else:
            print(f"{datetime.now():%H:%M:%S} no payload raw={raw!r}")
        time.sleep(1)
        set_active()
except KeyboardInterrupt:
    pass
finally:
    send("C")
    ser.close()
