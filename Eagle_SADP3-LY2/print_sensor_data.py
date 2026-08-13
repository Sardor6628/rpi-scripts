import serial
import time
from datetime import datetime

ser = serial.Serial("/dev/serial0", 115200, timeout=0.2)

# ── LDF constants (SADP3-LY2__LDF_2023-03-20.ldf) ───────────────────────────
FRAME_ID_SLAVE  = "07"   # SADP_Stat_LIN  (slave publishes, 8 bytes)
FRAME_ID_MASTER = "05"   # Placeholder    (master sends 8 zero bytes)
PLACEHOLDER_DATA = "0000000000000000"  # 8 bytes = 64 bits, all zero

# Signal encoding error / SNA sentinel values
ERR_8BIT   = (254, 255)
ERR_11BIT  = (2046, 2047)


def send(cmd, delay=0.05):
    ser.reset_input_buffer()
    ser.write((cmd + "\r").encode())
    time.sleep(delay)
    return ser.read_all().decode(errors="ignore").strip()


def decode_sadp(rx):
    """Decode the 8-byte SADP_Stat_LIN frame response."""
    if not rx.startswith("M"):
        return None

    hexstr = "".join(c for c in rx if c in "0123456789ABCDEFabcdef").upper()

    # Locate frame ID 07 in the response
    idx = hexstr.find(FRAME_ID_SLAVE.upper())
    if idx < 0:
        return None

    payload = hexstr[idx + 2:]
    if len(payload) < 16:          # 8 bytes = 16 hex chars
        return None

    d = bytes.fromhex(payload[:16])

    # ── Bit extraction per LDF signal layout ──────────────────────────────────
    # SADP_DewPointTemp   : bits  0-7   → byte 0
    dew_pt_raw       = d[0]

    # SADP_RH             : bits  8-15  → byte 1
    rh_raw           = d[1]

    # SADP_AmbTemp        : bits 16-23  → byte 2
    amb_raw          = d[2]

    # SADP_DewPointTemp_HiRes : bits 24-34 (11 bits)
    dew_hires_raw    = d[3] | ((d[4] & 0x07) << 8)

    # SADP_Reserved1      : bit 35  (bit 3 of byte 4)
    # SADP_TempAmb_HiRes  : bits 36-46 (11 bits)
    amb_hires_raw    = ((d[4] >> 4) & 0x0F) | ((d[5] & 0x7F) << 4)

    # SADP_Reserved2      : bits 61-62 (bits 5-6 of byte 7)
    # SADP_RsErr          : bit 63    (bit 7 of byte 7)
    rs_err           = (d[7] >> 7) & 0x01

    # ── Physical value conversion ─────────────────────────────────────────────
    def to_degC_8bit(raw):
        if raw in ERR_8BIT:
            return None
        return raw * 0.5 - 40.0

    def to_degC_11bit(raw):
        if raw in ERR_11BIT:
            return None
        return raw * 0.1 - 40.0

    def to_rh(raw):
        if raw in ERR_8BIT:
            return None
        return raw * 0.5

    return {
        "amb_temp":      to_degC_8bit(amb_raw),
        "amb_temp_hi":   to_degC_11bit(amb_hires_raw),
        "dew_pt":        to_degC_8bit(dew_pt_raw),
        "dew_pt_hi":     to_degC_11bit(dew_hires_raw),
        "rh":            to_rh(rh_raw),
        "rs_err":        rs_err,
    }


def fmt(val, unit, decimals=1):
    return f"{val:.{decimals}f}{unit}" if val is not None else "N/A"


# ── Initialise LIN bus (same speed as LDF: 19.2 kbps = S3) ──────────────────
print(send("V", 0.2))   # firmware version
send("S3")               # 19.2 kbit/s
send("O")                # open LIN bus

try:
    while True:
        # Send the Placeholder master frame to trigger a slave response
        send(f"T{FRAME_ID_MASTER}{PLACEHOLDER_DATA}")

        # Request the slave-published status frame
        rx = send(f"r{FRAME_ID_SLAVE}")

        data = decode_sadp(rx)
        if data:
            print(
                f"{datetime.now():%H:%M:%S} "
                f"T={fmt(data['amb_temp_hi'], '°C')} "
                f"({fmt(data['amb_temp'], '°C')}) "
                f"RH={fmt(data['rh'], '%')} "
                f"DP={fmt(data['dew_pt_hi'], '°C')} "
                f"RsErr={data['rs_err']}"
            )
        else:
            print(f"{datetime.now():%H:%M:%S} no valid frame  raw={rx!r}")

        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")
    send("C")    # close LIN bus
    ser.close()
