import serial
import time

ser = serial.Serial("/dev/serial0", 115200, timeout=0.2)

def send_cmd(cmd):
    ser.write((cmd + "\r").encode())
    time.sleep(0.05)
    return ser.read_all().decode(errors="ignore").strip()

send_cmd("V")
send_cmd("S3")
send_cmd("O")

print("Scanning for active LIN nodes...")

# Try reading standard diagnostic IDs (0x3C / 0x3D) or broadcasting a wild header
for frame_id in [0x2B, 0x3C, 0x3D]:
    hex_str = format(frame_id, '02X')
    send_cmd(f"T{hex_str}0000000000000000")
    resp = send_cmd(f"r{hex_str}")
    print(f"Checking ID 0x{hex_str}: Response -> '{resp}'")

ser.close()
