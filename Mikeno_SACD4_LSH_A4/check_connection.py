import serial, time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

def send(cmd, delay=0.06):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()

def set_active():
    # A4 style command seen in your configs/scripts
    pressure = 600
    b0 = 1 | ((pressure & 0x03) << 6)   # mode=1 active
    b1 = (pressure >> 2) & 0xFF
    payload = f"{b0:02X}{b1:02X}" + "00"*6
    send(f"T1D8{payload}")

def read_1f():
    rx = send("r1F", 0.15)
    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find("1F")
    if i < 0 or len(h) < i + 2 + 16:
        return None, rx
    data_hex = h[i+2:i+18]   # 8-byte payload
    return data_hex, rx

print(send("V", 0.2))
send("S3")
send("O")

try:
    set_active()
    time.sleep(1)
    while True:
        data_hex, raw = read_1f()
        if data_hex:
            print(f"{datetime.now():%H:%M:%S} DATA id=1F payload={data_hex} raw={raw}")
        else:
            print(f"{datetime.now():%H:%M:%S} no payload raw={raw!r}")
        time.sleep(1)
        set_active()
except KeyboardInterrupt:
    pass
finally:
    send("C")
    ser.close()
