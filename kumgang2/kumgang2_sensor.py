import serial
import time
from datetime import datetime
from sensirion_i2c_driver import I2cConnection
from sensirion_sensorbridge_i2c_driver import SensorBridgeI2cDevice
from sensirion_i2c_sht.sht4x import Sht4xI2cDevice
from sensirion_sensorbridge_driver import SensorBridge

SERIAL_PORTS = ['/dev/ttyUSB0', '/dev/ttyUSB1']
BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
SHT4X_ADDR = 0x44


def find_bridge():
    for port in SERIAL_PORTS:
        try:
            ser = serial.Serial(port, BAUDRATE, timeout=1)
            bridge = SensorBridge(ser)
            print(f"SensorBridge found on {port}")
            return bridge
        except (serial.SerialException, OSError):
            continue
    return None


bridge = find_bridge()
if bridge is None:
    print("ERROR: No SensorBridge found.")
    exit(1)

bridge.set_i2c_frequency(0, I2C_FREQ)
bridge.set_supply_voltage(0, SUPPLY_V)
bridge.switch_supply_on(0)
time.sleep(0.5)

i2c = SensorBridgeI2cDevice(bridge, port=0, slave_address=SHT4X_ADDR)
sensor = Sht4xI2cDevice(I2cConnection(i2c))

try:
    while True:
        temp, hum = sensor.single_shot_measurement()
        print(
            f"{datetime.now():%H:%M:%S}  "
            f"Temp={temp}  "
            f"Humidity={hum}"
        )
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")
    bridge.switch_supply_off(0)
