#!/bin/bash
# Setup script for Zinnwald SABM analog sensor measurement
set -e

echo "=== Zinnwald SABM Analog Sensor Setup ==="

# Install UL for Linux C API (prerequisite for uldaq Python package)
if ! ldconfig -p | grep -q libuldaq; then
    echo "Installing UL for Linux C library..."
    sudo apt-get update
    sudo apt-get install -y libusb-1.0-0-dev build-essential
    cd /tmp
    wget -q https://github.com/mccdaq/uldaq/releases/download/v1.2.1/libuldaq-1.2.1.tar.bz2
    tar -xjf libuldaq-1.2.1.tar.bz2
    cd libuldaq-1.2.1
    ./configure && make && sudo make install
    sudo ldconfig
    cd -
    echo "UL for Linux C library installed."
else
    echo "UL for Linux C library already installed."
fi

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Add udev rule for MCC USB devices (non-root access)
UDEV_RULE="/etc/udev/rules.d/99-mcc.rules"
if [ ! -f "$UDEV_RULE" ]; then
    echo "Adding udev rule for MCC DAQ devices..."
    echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="09db", MODE="0666"' | sudo tee "$UDEV_RULE"
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "Udev rule added. You may need to reconnect the DAQ device."
fi

echo ""
echo "=== Setup Complete ==="
echo "Activate the environment with: source venv/bin/activate"
echo "Run measurement:  python print_sensor_data.py --channel 0 --label Zinnwald_Wall"
echo "Run dashboard:    python dashboard.py --channel 0 --label Zinnwald_Wall"
