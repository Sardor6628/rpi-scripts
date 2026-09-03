# Zinnwald SABM Analog Sensor - Sensor Wall

Reads analog voltage from a Zinnwald (SABM family) sensor via MCC USB-1208FS-Plus DAQ.

## Hardware

- **Sensor**: Zinnwald (SABM family) — analog voltage output
- **DAQ**: MCC USB-1208FS-Plus (8 single-ended / 4 differential analog inputs, 12-bit)
- **Connection**: USB from DAQ to host PC

## Setup

```bash
chmod +x setup.sh
./setup.sh
```

## Usage

### Console output (table mode)
```bash
source venv/bin/activate
python print_sensor_data.py --channel 0 --label Zinnwald_Wall
```

### CSV output (for logging)
```bash
python print_sensor_data.py --channel 0 --label Zinnwald_Wall --csv >> data.csv
```

### Rich dashboard
```bash
python dashboard.py --channel 0 --label Zinnwald_Wall
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--channel` | 0 | Analog input channel (0-7 single-ended) |
| `--mode` | se | Input mode: `se` (single-ended) or `diff` (differential) |
| `--range` | bip10v | Voltage range: `bip10v`, `bip5v`, `bip2v`, `bip1v` |
| `--label` | Zinnwald | Measurement label |
| `--interval` | 1.0 | Sampling interval in seconds |
| `--csv` | off | Output CSV format (print_sensor_data.py only) |
