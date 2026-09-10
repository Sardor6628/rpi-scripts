# SEN66 RPi Measurement Scripts

Standalone SEN66 sensor measurement via Sensirion SensorBridge on Raspberry Pi.
**No SensiLab access required** — uses only public PyPI packages.

## Measured quantities

Indoor air quality: PM1.0/2.5/4.0/10, VOC index, NOx index, CO₂, temperature
and relative humidity — all from the single SEN66 module.

## Hardware

- Raspberry Pi (any model with USB)
- Sensirion SensorBridge (SEK-SensorBridge)
- Sensirion SEN66 sensor connected to SensorBridge port

## Installation

```bash
# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install dependencies (all from public PyPI)
pip install -r requirements.txt
```

## Usage

### Print sensor data to console

```bash
# default setup (SensorBridge port 1)
python print_sensor_data.py --label SEN66 --port /dev/ttyUSB0

# sensor on SensorBridge port 2
python print_sensor_data.py --label SEN66 --port /dev/ttyUSB0 --bridge-port 2

# CSV output for logging
python print_sensor_data.py --label SEN66 --csv > measurements.csv
```

### Live terminal dashboard

```bash
python dashboard.py --port /dev/ttyUSB0
python dashboard.py --port /dev/ttyUSB0 --bridge-port 2
```

## SEN66 Measured Values

| Parameter   | Unit   | Description                     |
|-------------|--------|---------------------------------|
| PM 1.0      | µg/m³  | Particulate matter ≤1.0 µm      |
| PM 2.5      | µg/m³  | Particulate matter ≤2.5 µm      |
| PM 4.0      | µg/m³  | Particulate matter ≤4.0 µm      |
| PM 10       | µg/m³  | Particulate matter ≤10 µm       |
| Temperature | °C     | Ambient temperature             |
| Humidity    | %RH    | Relative humidity               |
| VOC Index   | 1-500  | Volatile organic compounds      |
| NOx Index   | 1-500  | Nitrogen oxides                 |
| CO₂         | ppm    | Carbon dioxide concentration    |

## Wiring

Connect SEN66 to SensorBridge port 1 (or port 2) using the ribbon cable.
SensorBridge connects to RPi via USB (appears as `/dev/ttyUSB0`).

## Troubleshooting

- **Permission denied on /dev/ttyUSB0**: Add user to `dialout` group:
  `sudo usermod -aG dialout $USER` then re-login.
- **No device found**: Check `ls /dev/ttyUSB*` — the port may be `ttyUSB1`.
- **NaN readings**: SEN66 needs ~30s warm-up after power-on.
