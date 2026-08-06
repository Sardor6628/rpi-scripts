import serial
import time

# Open the serial port matching your hardware connection
ser = serial.Serial("/dev/serial0", 115200, timeout=0.2)

def send_command(cmd, delay=0.1):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()

print("Initializing LIN interface...")
print("Version:", send_command("V", 0.2))

# Set baud rate to 19.2 kbps as required by the LDF
print("Setting baudrate to 19.2k...")
print(send_command("S3", 0.2))

# Open the LIN bus channel
print("Opening LIN bus...")
print(send_command("O", 0.2))

print("\nListening for live LIN frames... Press Ctrl+C to exit.\n")

try:
    while True:
        # Request or read frame 43 (0x2B hex)
        response = send_command("r2B", 0.1)
        if response:
            print(f"Received raw: {response}")
        else:
            print("No data received on bus...")
        time.sleep(0.12)

except KeyboardInterrupt:
    print("\nClosing LIN bus...")
    send_command("C", 0.1)
    ser.close()
    print("Done.")