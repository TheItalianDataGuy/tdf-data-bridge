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
from security_utils import is_authorized_mac, is_valid_opcode, is_throttled
from security_utils import init_security_config
import json


try:
    from bleak import BleakServer, BleakService, BleakCharacteristic
    from bleak.backends.device import BLEDevice
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError:
    BleakServer = None

FE_C_DEVICE_TYPE = 17

last_sent_incline = None
log_file = "ride_log.csv"
last_ble_data = b"\x00"

ble_characteristic = None
control_point_characteristic = None
serial_port_global = None

current_resistance = 10
current_incline = 0.0
current_gear = (1, 1)  # (front, rear)

# Detect the USB serial port connected to the bike

def auto_detect_serial_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if "SLAB" in port.description or "CP210" in port.description:
            return port.device
    logging.warning("No compatible serial port detected.")
    return None


# Send incline grade to bike using ASCII command

def send_incline_command(grade, serial_port):
    global last_sent_incline
    if not (-10 <= grade <= 20):
        return
    if last_sent_incline is not None and abs(grade - last_sent_incline) < 1:
        return
    last_sent_incline = grade
    sign = '+' if grade >= 0 else '-'
    value = f"{abs(int(round(grade))):02d}"
    cmd = f"G{sign}{value}\r\n".encode("ascii")
    try:
        with serial.Serial(serial_port, 115200, timeout=1, exclusive=True) as ser:
            ser.write(cmd)
    except serial.SerialException as e:
        logging.error(f"[Serial Error] Could not write to bike: {e}")

# Send resistance level (e.g. ERG mode)

def send_resistance_command(level, serial_port):
    cmd = f"R{level:02d}\r\n".encode("ascii")
    try:
        with serial.Serial(serial_port, 115200, timeout=1) as ser:
            ser.write(cmd)
    except serial.SerialException as e:
        logging.error(f"[Serial Error] Could not write resistance: {e}")

# Simulated gear shift control

def send_gear(front, rear, serial_port):
    cmd = f"G{front}{rear}\r\n".encode("ascii")
    try:
        with serial.Serial(serial_port, 115200, timeout=1) as ser:
            ser.write(cmd)
    except serial.SerialException as e:
        logging.error(f"[Serial Error] Could not set gear: {e}")

# Called every time new ANT+ data is received

def estimate_speed_from_cadence(cadence, gear_ratio=2.5):
    return round(cadence * gear_ratio / 60.0 * 3.6, 1)

def on_data(data, serial_port):
    global ble_characteristic, current_resistance, current_incline, current_gear
    power = data[7] | (data[8] << 8)
    cadence = data[10]
    speed = estimate_speed_from_cadence(cadence)
    raw_grade = data[5] | (data[6] << 8)
    percent_grade = raw_grade / 100.0
    if percent_grade < 0:
        mapped_grade = percent_grade * 0.5
    elif percent_grade > 10:
        mapped_grade = 10 + (percent_grade - 10) * 0.3
    else:
        mapped_grade = percent_grade
    incline = max(-10, min(20, int(round(mapped_grade))))
    current_incline = incline
    logging.info(f"Power: {power} W, Cadence: {cadence} rpm, Speed: {speed} kph, Incline: {incline}%")
    with open(log_file, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([time.time(), power, cadence, speed, incline])
    send_incline_command(incline, serial_port)

    # Notify FTMS-compatible client (BLE)
    if ble_characteristic and ble_characteristic.properties and "notify" in ble_characteristic.properties:
        try:
            flags = 0b0000001111111111
            notify_data = bytearray()
            notify_data.append(flags & 0xFF)
            notify_data.append((flags >> 8) & 0xFF)
            notify_data += int(speed * 100).to_bytes(2, byteorder='little')
            notify_data += int(cadence * 2).to_bytes(2, byteorder='little')
            notify_data += int(power).to_bytes(2, byteorder='little')
            notify_data += int(current_incline * 10).to_bytes(2, byteorder='little', signed=True)
            notify_data += int(current_resistance).to_bytes(2, byteorder='little')
            notify_data += bytes(current_gear)
            ble_characteristic.value = notify_data
            logging.debug(f"[BLE Notify FTMS] Sent: {list(notify_data)}")
        except Exception as e:
            logging.error(f"[BLE Notify] Failed to send: {e}")

# Handles incoming control commands from BLE FTMS Control Point
def handle_control_command(data: bytearray):
    global serial_port_global, current_resistance, current_gear, control_point_characteristic

    # Validate packet structure to prevent malformed data issues
    if not isinstance(data, bytearray) or len(data) < 2:
        logging.warning("[BLE Control] Invalid or malformed command received")
        return

    def send_ack(opcode, result=0x01):
        if control_point_characteristic:
            response = bytearray([0x80, opcode, result])
            control_point_characteristic.value = response

    opcode = data[0]
    param = data[1]

    if opcode == 0x05:
        incline = int(param) / 10.0
        logging.info(f"[BLE Control] Set target incline: {incline}%")
        send_incline_command(incline, serial_port_global)
        send_ack(opcode)
    elif opcode == 0x30:
        resistance = int(param)
        current_resistance = resistance
        logging.info(f"[BLE Control] Set resistance level: {resistance}")
        send_resistance_command(resistance, serial_port_global)
        send_ack(opcode)
    elif opcode == 0x40 and len(data) >= 3:
        front = data[1]
        rear = data[2]
        current_gear = (front, rear)
        logging.info(f"[BLE Control] Set gear: Front {front}, Rear {rear}")
        send_gear(front, rear, serial_port_global)
        send_ack(opcode)
    else:
        logging.info(f"[BLE Control] Unhandled opcode: {opcode}")

# Secure BLE write handler used to process FTMS control commands from Zwift or similar apps

def on_write(device: BLEDevice, _: BleakGATTCharacteristic, data: bytearray):
    if not is_authorized_mac(device.address):
        logging.warning(f"[SECURITY] Unauthorized BLE device: {device.address}")
        return
    if is_throttled(device.address):
        logging.warning(f"[SECURITY] Rate limit exceeded for {device.address}")
        return
    if not isinstance(data, bytearray) or len(data) < 2:
        logging.warning("[SECURITY] Malformed data received")
        return
    opcode = data[0]
    if not is_valid_opcode(opcode):
        logging.warning(f"[SECURITY] Invalid opcode: {opcode}")
        return

    logging.debug(f"[BLE Control] Accepted command {list(data)} from {device.address}")
    
    try:
        handle_control_command(data)
    except Exception as e:
        logging.error(f"[BLE Control] Failed to process command {list(data)}: {e}")



# Initializes BLE FTMS GATT service with notify and control support

async def start_ble_ftms():
    global ble_characteristic, control_point_characteristic
    if BleakServer is None:
        logging.error("Bleak or platform support for BLE not found.")
        return
    logging.info("[BLE] Starting FTMS broadcasting service...")
    FTMS_UUID = "1826"
    DATA_UUID = "2AD9"
    CONTROL_UUID = "2AD8"
    ble_characteristic = BleakCharacteristic(DATA_UUID, ["notify"], value=b"\x00")
    control_point_characteristic = BleakCharacteristic(CONTROL_UUID, ["write"], value=b"\x00")
    
    # Use secure write handler defined earlier
    control_point_characteristic.set_write_callback(on_write)

    service = BleakService(FTMS_UUID)
    service.add_characteristic(ble_characteristic)
    service.add_characteristic(control_point_characteristic)
    logging.info("[BLE] FTMS GATT service initialized with control support")
    await asyncio.sleep(1)
    logging.info("[BLE] (Simulation) BLE notifications and control active")


# Program entry point

def main():
    global serial_port_global

    # --- CLI argument parsing ---
    parser = argparse.ArgumentParser(description="TDF Data Bridge")
    parser.add_argument("--ant", default="usb:0", help="ANT+ device path")
    parser.add_argument("--incline", help="Serial port for incline control")
    parser.add_argument("--ble", action="store_true", help="Enable BLE FTMS broadcasting")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    args = parser.parse_args()

    # --- Logging configuration ---
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # --- Load config.json ---
    try:
        with open(args.config, "r") as f:
            config = json.load(f)
        init_security_config(config)  
    except Exception as e:
        logging.error(f"Failed to load config file: {e}")
        return
    
    # --- Serial port setup ---
    serial_port = args.incline or auto_detect_serial_port()
    serial_port_global = serial_port
    if not serial_port:
        logging.error("No serial port found. Specify --incline manually.")
        return
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
