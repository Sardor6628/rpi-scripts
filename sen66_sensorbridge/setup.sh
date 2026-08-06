#!/bin/bash
# Install script for Raspberry Pi (run once)
set -e

echo "=== SEN66 RPi Scripts Setup ==="

# Create virtualenv if not exists
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

echo "Installing packages from public PyPI..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Setup complete ==="
echo "Activate with: source venv/bin/activate"
echo "Run: python print_sensor_data.py --label PM_Halla"
echo "  or: python dashboard.py --label Eagle"
