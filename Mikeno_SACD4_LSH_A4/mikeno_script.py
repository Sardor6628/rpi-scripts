import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.25)

FRAME_CTRL = "1D"
FRAME_DATA = "1F"

def send(cmd, delay=0.06):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()

def set_active_once():
    # proven A4-style control payload from your old setup
    # mode=1 + pressure=600(raw packed) + rest 0
    return send("T1D80196000000000000")

def get_bits(v, s, n):
    return (v >> s) & ((1 << n) - 1)

def decode(rx):
    if not rx.startswith("M"):
        return None
    h = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()
    i = h.find(FRAME_DATA)
    if i < 0 or len(h) < i + 18:
        return None

    payload = h[i+2:i+18]
    v = int.from_bytes(bytes.fromhex(payload), "little")

    co2_raw = get_bits(v, 0, 10)
    alarm   = get_bits(v,10, 2)
    bz      = get_bits(v,12, 4)
    grad    = get_bits(v,16,10)
    press   = get_bits(v,26,10)
    re      = get_bits(v,36, 1)
    defect  = get_bits(v,37, 1)
    rt_raw  = get_bits(v,40,16)

    co2_ppm = None if co2_raw in (1022, 1023) else co2_raw * 0.01 * (1_000_000.0 / 101.325)
    grad_v  = None if grad in (1022, 1023) else grad * 100 - 50000
    p_mbar  = None if press in (1021, 1022, 1023) else press + 400
    rt_s    = None if rt_raw in (65534, 65535) else rt_raw * 10

    return payload, co2_raw, co2_ppm, alarm, bz, grad, grad_v, press, p_mbar, rt_s, defect, re

print(send("V", 0.2))
send("S3")
send("O")
print("CTRL:", set_active_once())

# let sensor settle
time.sleep(10)

last_keepalive = time.time()

try:
    while True:
        rx = send("r1F", 0.15)
        d = decode(rx)
        ts = datetime.now().strftime("%H:%M:%S")

        if d:
            payload, co2_raw, co2_ppm, alarm, bz, grad, grad_v, press, p_mbar, rt_s, defect, re = d
            print(
                f"{ts} raw={payload} "
                f"CO2raw={co2_raw} CO2={'N/A' if co2_ppm is None else f'{co2_ppm:.0f}ppm'} "
                f"Alarm={alarm} BZ={bz} "
                f"GradRaw={grad} Grad={'N/A' if grad_v is None else grad_v} "
                f"PRaw={press} P={'N/A' if p_mbar is None else f'{p_mbar}mbar'} "
                f"RT={'N/A' if rt_s is None else f'{rt_s}s'} Def={defect} RE={re}"
            )
        else:
            print(f"{ts} no valid frame raw={rx!r}")

        # keepalive rarely
        if time.time() - last_keepalive > 30:
            set_active_once()
            last_keepalive = time.time()

        time.sleep(1)

except KeyboardInterrupt:
    pass
finally:
    send("T1D80000000000000000")  # mode 0
    send("C")
    ser.close()
