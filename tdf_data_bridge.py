import serial
import argparse
import logging
import time
import csv
import os
from openant.easy.node import Node
from openant.easy.channel import Channel
import serial.tools.list_ports
import asyncio

try:
    from bleak import BleakServer, BleakService, BleakCharacteristic
    from bleak.backends.device import BLEDevice
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError:
    BleakServer = None

# ANT+ FE-C device type constant (normally 0x11 or 17)
FE_C_DEVICE_TYPE = 17

last_sent_incline = None  # For smoothing
log_file = "ride_log.csv"  # CSV log file path
last_ble_data = b"\x00"  # Default BLE data state

ble_characteristic = None  # Reference to BLE characteristic for notifications

# Function to auto-detect serial port based on ProForm characteristics
def auto_detect_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "SLAB" in port.description or "CP210" in port.description:
            return port.device
    return None

# Function to send incline commands with smoothing and error handling
def send_incline_command(grade, serial_port):
    global last_sent_incline

    if not (-10 <= grade <= 20):
        return
    if last_sent_incline is not None and abs(grade - last_sent_incline) < 1:
        return  # Skip small changes for smoothing
    last_sent_incline = grade

    sign = '+' if grade >= 0 else '-'
    value = f"{abs(int(round(grade))):02d}"
    cmd = f"G{sign}{value}\r\n".encode("ascii")

    try:
        with serial.Serial(serial_port, 115200, timeout=1) as ser:
            ser.write(cmd)
    except serial.SerialException as e:
        logging.error(f"[Serial Error] Could not write to bike: {e}")

# ANT+ data callback: maps grade, logs metrics, sends incline to bike
def on_data(data, serial_port):
    global ble_characteristic

    power = data[7] | (data[8] << 8)
    cadence = data[10]
    speed = data[9]  # assuming speed is provided in byte 9 (for simulation)
    raw_grade = data[5] | (data[6] << 8)
    percent_grade = raw_grade / 100.0

    if percent_grade < 0:
        mapped_grade = percent_grade * 0.5
    elif percent_grade > 10:
        mapped_grade = 10 + (percent_grade - 10) * 0.3
    else:
        mapped_grade = percent_grade

    incline = max(-10, min(20, int(round(mapped_grade))))

    logging.info(f"Power: {power} W, Cadence: {cadence} rpm, Speed: {speed} kph, Incline: {incline}%")

    # Append log to CSV
    with open(log_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([time.time(), power, cadence, speed, incline])

    send_incline_command(incline, serial_port)

    # Notify BLE clients with updated data
    if ble_characteristic and ble_characteristic.properties and "notify" in ble_characteristic.properties:
        try:
            notify_data = bytearray([
                power & 0xFF, (power >> 8) & 0xFF,
                cadence & 0xFF,
                speed & 0xFF,
                incline & 0xFF
            ])
            ble_characteristic.value = notify_data
            logging.debug(f"[BLE Notify] Sent: {list(notify_data)}")
        except Exception as e:
            logging.error(f"[BLE Notify] Failed to send: {e}")

# BLE FTMS Service Definition (with notifications)
async def start_ble_ftms():
    global ble_characteristic

    if BleakServer is None:
        logging.error("Bleak or platform support for BLE not found.")
        return

    logging.info("[BLE] Starting FTMS broadcasting service...")

    # Define FTMS service UUID and characteristics
    FTMS_UUID = "1826"
    CHARACTERISTIC_UUID = "2AD9"  # Indoor Bike Data

    ble_characteristic = BleakCharacteristic(CHARACTERISTIC_UUID, ["notify"], value=b"\x00")
    service = BleakService(FTMS_UUID)
    service.add_characteristic(ble_characteristic)

    logging.info("[BLE] FTMS GATT service initialized")
    await asyncio.sleep(1)
    logging.info("[BLE] (Simulation) BLE notifications active")

# Main execution
def main():
    parser = argparse.ArgumentParser(description="TDF Data Bridge")
    parser.add_argument("--ant", default="usb:0", help="ANT+ device path")
    parser.add_argument("--incline", help="Serial port for incline control")
    parser.add_argument("--ble", action="store_true", help="Enable BLE FTMS broadcasting")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)

    # Auto-detect serial port if not provided
    serial_port = args.incline or auto_detect_serial_port()
    if not serial_port:
        logging.error("No serial port found. Specify --incline manually.")
        return

    # Create CSV log header if file doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["timestamp", "power", "cadence", "speed", "incline"])

    if args.ble:
        loop = asyncio.get_event_loop()
        loop.create_task(start_ble_ftms())

    node = Node()
    network = node.get_free_network()
    network.set_key(0xB9, [0]*8)

    channel = node.new_channel(Channel.Type.BIDIRECTIONAL_RECEIVE)
    channel.set_period(8182)
    channel.set_search_timeout(255)
    channel.set_rf_freq(57)
    channel.set_id(0, 0, 0)
    channel.set_device_type(FE_C_DEVICE_TYPE)

    channel.on_broadcast_data = lambda data: on_data(data, serial_port)

    node.start()
    channel.open()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        logging.info("Stopped.")
        channel.close()
        node.stop()

if __name__ == "__main__":
    main()
