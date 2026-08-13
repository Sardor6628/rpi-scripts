import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.2)

def send(cmd, delay=0.05):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()

def decode_pm(rx):
    if not rx.startswith("M"):
        return None

    hexstr = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()

    idx = hexstr.find("1A")
    if idx < 0:
        return None

    payload = hexstr[idx + 2:]

    if len(payload) < 10:
        return None

    data = bytes.fromhex(payload[:10])

    b0, b1, b2, b3, b4 = data

    resp_err = b0 & 0x01
    status = (b0 >> 1) & 0x07

    pm25 = b1 | ((b2 & 0x03) << 8)
    pm10 = b3 | ((b4 & 0x03) << 8)

    status_map = {
        0: "Init",
        1: "Normal",
        2: "Limited",
        3: "Standby",
        4: "Error"
    }

    return {
        "status": status_map.get(status, str(status)),
        "resp_err": resp_err,
        "pm25": pm25,
        "pm10": pm10
    }

print(send("V", 0.2))

send("S3")      # 19.2 kbit per LDF
send("O")       # Open LIN

try:
    while True:

        # Enable sensor
        send("T1D101")

        # Read PM frame (0x1A)
        rx = send("r1A")

        data = decode_pm(rx)

        if data:
            print(
                f"{datetime.now():%H:%M:%S}  "
                f"Status={data['status']}  "
                f"PM2.5={data['pm25']}  "
                f"PM10={data['pm10']}  "
                f"Err={data['resp_err']}"
            )

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")
    send("T1D100")
    send("C")
    ser.close()
