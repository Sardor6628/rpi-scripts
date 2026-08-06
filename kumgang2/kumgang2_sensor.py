import math
import time
from datetime import datetime
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
    SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_sht.sht4x import Sht4xI2cDevice

SERIAL_PORTS = ['/dev/ttyUSB0', '/dev/ttyUSB1']
BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
BRIDGE_PORT = SensorBridgePort.ONE


def find_bridge():
    for port in SERIAL_PORTS:
        try:
            serial_port = ShdlcSerialPort(port, BAUDRATE)
            bridge = SensorBridgeShdlcDevice(
                ShdlcConnection(serial_port), slave_address=0
            )
            print(f"SensorBridge found on {port}")
            return bridge
        except Exception:
            continue
    return None


bridge = find_bridge()
if bridge is None:
    print("ERROR: No SensorBridge found.")
    exit(1)

bridge.set_i2c_frequency(BRIDGE_PORT, I2C_FREQ)
bridge.set_supply_voltage(BRIDGE_PORT, SUPPLY_V)
bridge.switch_supply_on(BRIDGE_PORT)
time.sleep(0.5)

i2c_proxy = SensorBridgeI2cProxy(bridge, port=BRIDGE_PORT)
sensor = Sht4xI2cDevice(I2cConnection(i2c_proxy))


def calc_dewpoint(temp_c, rh):
    """Magnus formula for dewpoint (TWS)."""
    a = 17.625
    b = 243.04
    alpha = (a * temp_c) / (b + temp_c) + math.log(rh / 100.0)
    return (b * alpha) / (a - alpha)


try:
    while True:
        temp, hum = sensor.single_shot_measurement()
        t = float(str(temp).split()[0])
        h = float(str(hum).split()[0])
        tws = calc_dewpoint(t, h)
        print(
            f"{datetime.now():%H:%M:%S}  "
            f"Temp={t:.2f} °C  "
            f"Humidity={h:.2f} %RH  "
            f"TWS={tws:.2f} °C"
        )
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")
    bridge.switch_supply_off(BRIDGE_PORT)
