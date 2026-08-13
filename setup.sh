#!/bin/bash
# =============================================================================
# Combined setup script for the whole rpi-scripts project.
#
# Creates ONE shared virtual environment (venv) at the project root and installs
# all Python dependencies for every sub-project:
#   - Eagle_SADP3-LY2        (serial)
#   - Mikeno_SACD4_LSH_A4    (serial)
#   - PM_Halla               (serial)
#   - kumgang2               (Sensirion SHT4x)
#   - sen66_sensorbridge     (Sensirion SEN66)
#   - zinnwald_sabm_analog   (MCC USB-1208FS-Plus DAQ / uldaq)
#
# Run once from the project root:  bash setup.sh
# =============================================================================
set -e

echo "=== rpi-scripts combined setup ==="

# -----------------------------------------------------------------------------
# 1. System packages
#    - python3-venv / python3-full : virtual environment support
#    - python3-tk                  : tkinter (for the *_dashboard.py GUIs)
#    - libusb-1.0-0-dev, build-essential : needed to build libuldaq
# -----------------------------------------------------------------------------
echo "Installing required system packages..."
sudo apt-get update
sudo apt-get install -y python3-full python3-venv python3-tk \
    libusb-1.0-0-dev build-essential wget

# -----------------------------------------------------------------------------
# 2. UL for Linux C library (prerequisite for the uldaq Python package)
#    Used by zinnwald_sabm_analog. Skipped if already installed.
# -----------------------------------------------------------------------------
if ! ldconfig -p | grep -q libuldaq; then
    echo "Installing UL for Linux C library (libuldaq)..."
    cd /tmp
    wget -q https://github.com/mccdaq/uldaq/releases/download/v1.2.1/libuldaq-1.2.1.tar.bz2
    tar -xjf libuldaq-1.2.1.tar.bz2
    cd libuldaq-1.2.1
    ./configure && make && sudo make install
    sudo ldconfig
    cd -
    echo "libuldaq installed."
else
    echo "libuldaq already installed."
fi

# Return to the directory of this script (project root)
cd "$(dirname "$0")"

# -----------------------------------------------------------------------------
# 3. Shared virtual environment
#    --system-site-packages lets the venv access the system tkinter (python3-tk),
#    which cannot be installed via pip.
# -----------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "Creating shared virtual environment..."
    python3 -m venv --system-site-packages venv
fi

source venv/bin/activate

# -----------------------------------------------------------------------------
# 4. Python dependencies
# -----------------------------------------------------------------------------
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# -----------------------------------------------------------------------------
# 5. udev rule for MCC USB DAQ devices (non-root access)
#    Used by zinnwald_sabm_analog.
# -----------------------------------------------------------------------------
UDEV_RULE="/etc/udev/rules.d/99-mcc.rules"
if [ ! -f "$UDEV_RULE" ]; then
    echo "Adding udev rule for MCC DAQ devices..."
    echo 'SUBSYSTEM=="usb", ATTR{idVendor}=="09db", MODE="0666"' | sudo tee "$UDEV_RULE"
    sudo udevadm control --reload-rules
    sudo udevadm trigger
    echo "Udev rule added. You may need to reconnect the DAQ device."
fi

echo ""
echo "=== Setup complete ==="
echo "Activate the shared environment with:  source venv/bin/activate"
echo ""
echo "Then run any sub-project, e.g.:"
echo "  python zinnwald_sabm_analog/print_sensor_data.py --channel 0 --label Zinnwald_Wall"
echo "  python sen66_sensorbridge/print_sensor_data.py --label PM_Halla"
echo "  python kumgang2/print_sensor_data.py"
