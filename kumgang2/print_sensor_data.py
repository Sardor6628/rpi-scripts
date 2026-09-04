import time
from glob import glob
from datetime import datetime
from sensirion_shdlc_driver import ShdlcSerialPort, ShdlcConnection
from sensirion_shdlc_sensorbridge import (
    SensorBridgePort,
    SensorBridgeShdlcDevice,
    SensorBridgeI2cProxy,
)
from sensirion_i2c_driver import I2cConnection
from sensirion_i2c_sht.sht4x import Sht4xI2cDevice

BAUDRATE = 460800
I2C_FREQ = 100000
SUPPLY_V = 3.3
BRIDGE_PORT = SensorBridgePort.ONE


def candidate_ports():
    # The SensorBridge normally enumerates as ttyUSB* (FTDI), but scan ttyACM*
    # too so a differently-enumerated bridge is still found.
    return sorted(glob('/dev/ttyUSB*') + glob('/dev/ttyACM*'))


def find_bridge():
    ports = candidate_ports()
    if not ports:
        print("No /dev/ttyUSB* or /dev/ttyACM* devices present.")
        print("Check the USB cable and run: lsusb; dmesg | tail -30")
        return None, None

    for port in ports:
        serial_port = None
        try:
            serial_port = ShdlcSerialPort(port, BAUDRATE)
            bridge = SensorBridgeShdlcDevice(
                ShdlcConnection(serial_port), slave_address=0
            )
            # Opening the serial port succeeds for any USB device, so query the
            # firmware version to confirm this really is a SensorBridge.
            bridge.get_version()
            print(f"SensorBridge found on {port}")
            return bridge, serial_port
        except Exception as exc:
            print(f"  {port}: {exc}")
            if serial_port is not None:
                try:
                    serial_port.close()
                except Exception:
                    pass
            continue
    return None, None


bridge, serial_port = find_bridge()
if bridge is None:
    print("ERROR: No SensorBridge found.")
    exit(1)

bridge.set_i2c_frequency(BRIDGE_PORT, I2C_FREQ)
bridge.set_supply_voltage(BRIDGE_PORT, SUPPLY_V)
bridge.switch_supply_on(BRIDGE_PORT)
time.sleep(0.5)

i2c_proxy = SensorBridgeI2cProxy(bridge, port=BRIDGE_PORT)
sensor = Sht4xI2cDevice(I2cConnection(i2c_proxy))


try:
    while True:
        temp, hum = sensor.single_shot_measurement()
        print(
            f"{datetime.now():%H:%M:%S}  "
            f"Temp={temp.degrees_celsius:.2f} °C  "
            f"Humidity={hum.percent_rh:.2f} %RH"
        )
        time.sleep(1)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    try:
        bridge.switch_supply_off(BRIDGE_PORT)
    finally:
        serial_port.close()
