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
import random
import platform
from security_utils import (
    is_authorized_mac,
    is_valid_opcode,
    is_throttled,
    init_security_config,
)

try:
    from bleak import BleakServer, BleakService, BleakCharacteristic
    from bleak.backends.device import BLEDevice
    from bleak.backends.characteristic import BleakGATTCharacteristic
except ImportError:
    BleakServer = None

FE_C_DEVICE_TYPE = 17

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config.json"))


class BikeController:
    """
    Handles serial communication with the ProForm TDF bike for incline, resistance, and gear control.
    """

    def __init__(self, port=None):
        self.port = port or self.auto_detect_serial_port()
        self.last_sent_incline = None

    def auto_detect_serial_port(self):
        """
        Automatically detects the serial port connected to the bike.
        """
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "SLAB" in port.description or "CP210" in port.description:
                logging.info(f"[BikeController] Auto-detected serial port: {port.device}")
                return port.device
        logging.warning("[BikeController] No compatible serial port detected.")
        return None

    def send_incline(self, grade):
        """
        Sends incline grade to the bike using ASCII protocol.
        """
        if self.port is None or not (-10 <= grade <= 20):
            return
        if self.last_sent_incline is not None and abs(grade - self.last_sent_incline) < 1:
            return
        self.last_sent_incline = grade
        sign = '+' if grade >= 0 else '-'
        value = f"{abs(int(round(grade))):02d}"
        cmd = f"G{sign}{value}\r\n".encode("ascii")
        self._write_to_bike(cmd, "[Incline]")

    def send_resistance(self, level):
        """
        Sends resistance level to the bike (e.g., for ERG mode).
        """
        if self.port is None:
            return
        cmd = f"R{level:02d}\r\n".encode("ascii")
        self._write_to_bike(cmd, "[Resistance]")

    def send_gear(self, front, rear):
        """
        Simulates a gear shift by sending front and rear gear values.
        """
        if self.port is None:
            return
        cmd = f"G{front}{rear}\r\n".encode("ascii")
        self._write_to_bike(cmd, "[Gear]")

    def _write_to_bike(self, command, label=""):
        """
        Internal helper to write a command to the bike's serial port.
        """
        try:
            with serial.Serial(self.port, 115200, timeout=1, exclusive=True) as ser:
                ser.write(command)
                logging.debug(f"{label} Sent: {command}")
        except serial.SerialException as e:
            logging.error(f"{label} Serial error: {e}")


class SensorDataProcessor:
    """
    Processes incoming ANT+ data, logs metrics, updates BLE clients, and commands the bike.
    """

    def __init__(self, bike_controller, log_file="ride_log.csv", ble_characteristic=None):
        self.bike = bike_controller
        self.log_file = log_file
        self.ble_characteristic = ble_characteristic
        self.current_resistance = 10
        self.current_incline = 0.0
        self.current_gear = (1, 1)

        # Create log file with header if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["timestamp", "power", "cadence", "speed", "incline"])

    def estimate_speed_from_cadence(self, cadence, gear_ratio=2.5):
        """
        Convert cadence (rpm) to estimated speed in km/h.
        """
        return round(cadence * gear_ratio / 60.0 * 3.6, 1)

    def process(self, data):
        """
        Main method called on each ANT+ data packet.
        Parses and logs metrics, controls the bike, and sends BLE updates.
        """
        power = data[7] | (data[8] << 8)
        cadence = data[10]
        speed = self.estimate_speed_from_cadence(cadence)

        raw_grade = data[5] | (data[6] << 8)
        percent_grade = raw_grade / 100.0
        mapped_grade = self._map_grade(percent_grade)
        incline = max(-10, min(20, int(round(mapped_grade))))
        self.current_incline = incline

        logging.info(f"Power: {power} W, Cadence: {cadence} rpm, Speed: {speed} kph, Incline: {incline}%")

        self._log_to_csv(power, cadence, speed, incline)
        self.bike.send_incline(incline)
        self._notify_ble(power, cadence, speed, incline)

    def _map_grade(self, percent_grade):
        """
        Custom logic to scale very steep grades for realism.
        """
        if percent_grade < 0:
            return percent_grade * 0.5
        elif percent_grade > 10:
            return 10 + (percent_grade - 10) * 0.3
        else:
            return percent_grade

    def _log_to_csv(self, power, cadence, speed, incline):
        """
        Appends data to the ride log CSV.
        """
        with open(self.log_file, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([time.time(), power, cadence, speed, incline])

    def _notify_ble(self, power, cadence, speed, incline):
        """
        Sends FTMS-compliant BLE notification to clients.
        """
        if self.ble_characteristic and self.ble_characteristic.properties and "notify" in self.ble_characteristic.properties:
            try:
                flags = 0b0000001111111111
                notify_data = bytearray()
                notify_data.append(flags & 0xFF)
                notify_data.append((flags >> 8) & 0xFF)
                notify_data += int(speed * 100).to_bytes(2, byteorder='little')
                notify_data += int(cadence * 2).to_bytes(2, byteorder='little')
                notify_data += int(power).to_bytes(2, byteorder='little')
                notify_data += int(incline * 10).to_bytes(2, byteorder='little', signed=True)
                notify_data += int(self.current_resistance).to_bytes(2, byteorder='little')
                notify_data += bytes(self.current_gear)
                self.ble_characteristic.value = notify_data
                logging.debug(f"[BLE Notify FTMS] Sent: {list(notify_data)}")
            except Exception as e:
                logging.error(f"[BLE Notify] Failed to send: {e}")


class BLEServiceManager:
    """
    Manages the BLE FTMS GATT service, including characteristic setup and write security.
    """

    def __init__(self, bike_controller, security_checker):
        self.bike = bike_controller
        self.security = security_checker
        self.ble_characteristic = None
        self.control_point_characteristic = None

    async def start(self):
        """
        Initializes the BLE FTMS service and starts advertising (simulated).
        """
        if BleakServer is None:
            logging.error("[BLE] Bleak is not available on this platform.")
            return

        if platform.system() == "Windows":
            logging.error("[BLE] FTMS server is not supported on Windows.")
            return

        logging.info("[BLE] Initializing FTMS GATT service...")
        FTMS_UUID = "1826"
        DATA_UUID = "2AD9"
        CONTROL_UUID = "2AD8"

        self.ble_characteristic = BleakCharacteristic(DATA_UUID, ["notify"], value=b"\x00")
        self.control_point_characteristic = BleakCharacteristic(CONTROL_UUID, ["write"], value=b"\x00")

        if hasattr(self.control_point_characteristic, "set_write_callback"):
            self.control_point_characteristic.set_write_callback(self._on_write)
        else:
            logging.error("[BLE] write-callback missing – notify-only mode enabled")
            # Still attach service for notify use

        service = BleakService(FTMS_UUID)
        service.add_characteristic(self.ble_characteristic)
        service.add_characteristic(self.control_point_characteristic)
        logging.info("[BLE] FTMS GATT service ready")

        await asyncio.sleep(1)
        logging.info("[BLE] (Simulated) BLE notifications active")

    def get_notify_characteristic(self):
        return self.ble_characteristic

    def _on_write(self, device: 'BLEDevice', _: 'BleakGATTCharacteristic', data: bytearray):
        """
        Secure handler for BLE FTMS control commands.
        Applies security checks and forwards to bike controller.
        """
        if not self.security.is_authorized_mac(device.address):
            logging.warning(f"[SECURITY] Unauthorized BLE device: {device.address}")
            return
        if self.security.is_throttled(device.address):
            logging.warning(f"[SECURITY] Rate limit exceeded: {device.address}")
            return
        if not isinstance(data, bytearray) or len(data) < 2:
            logging.warning("[SECURITY] Malformed BLE command received")
            return
        opcode = data[0]
        if not self.security.is_valid_opcode(opcode):
            logging.warning(f"[SECURITY] Invalid opcode received: {opcode}")
            return

        logging.debug(f"[BLE] Accepted command {list(data)} from {device.address}")

        try:
            self.bike.handle_control_command(data)
        except Exception as e:
            logging.error(f"[BLE] Failed to process control command: {e}")


class SecurityManager:
    """
    Wraps BLE security checks for MAC address validation, opcode filtering, and rate limiting.
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.initialized = False

    def load_config(self):
        """
        Loads and validates the config file, initializing internal security state.
        """
        import json
        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)

            required_keys = {"authorized_devices", "allowed_opcodes", "rate_limit_seconds"}
            if not required_keys.issubset(config.keys()):
                missing = required_keys - config.keys()
                logging.error(f"[SECURITY] Config missing keys: {missing}")
                return False

            init_security_config(config)
            self.initialized = True
            logging.info("[SECURITY] Security config loaded successfully.")
            return True

        except Exception as e:
            logging.error(f"[SECURITY] Failed to load config: {e}")
            return False

    def is_authorized_mac(self, mac: str) -> bool:
        return is_authorized_mac(mac)

    def is_valid_opcode(self, opcode: int) -> bool:
        return is_valid_opcode(opcode)

    def is_throttled(self, mac: str) -> bool:
        return is_throttled(mac)


class RideLogger:
    """
    Handles CSV logging of ride metrics such as power, cadence, speed, and incline.
    """

    def __init__(self, log_path: str = "ride_log.csv"):
        self.log_path = log_path
        self._initialize_log_file()

    def _initialize_log_file(self):
        """
        Creates the log file with headers if it doesn't already exist.
        """
        if not os.path.exists(self.log_path):
            try:
                with open(self.log_path, "w", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["timestamp", "power", "cadence", "speed", "incline"])
                logging.info(f"[LOGGER] Created new ride log at: {self.log_path}")
            except Exception as e:
                logging.error(f"[LOGGER] Failed to create log file: {e}")

    def log(self, power: int, cadence: int, speed: float, incline: float):
        """
        Logs a new entry to the CSV file.
        """
        try:
            with open(self.log_path, "a", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow([time.time(), power, cadence, speed, incline])
            logging.debug(f"[LOGGER] Logged data: {power}W, {cadence}rpm, {speed}kph, {incline}%")
        except Exception as e:
            logging.error(f"[LOGGER] Failed to write to log: {e}")


class AntPlusReceiver:
    """
    Manages the ANT+ communication setup and receives broadcast data from the FE-C device.
    """

    def __init__(self, device_type: int, serial_port: str, on_data_callback):
        self.device_type = device_type
        self.serial_port = serial_port
        self.on_data_callback = on_data_callback
        self.node = Node()
        self.channel = None

    def _configure_channel(self):
        """
        Configures the ANT+ channel with required settings.
        """
        network = self.node.get_free_network()
        network.set_key(0xB9, [0] * 8)
        self.channel = self.node.new_channel(Channel.Type.BIDIRECTIONAL_RECEIVE)
        self.channel.set_period(8182)
        self.channel.set_search_timeout(255)
        self.channel.set_rf_freq(57)
        self.channel.set_id(0, 0, 0)
        self.channel.set_device_type(self.device_type)
        self.channel.on_broadcast_data = lambda data: self.on_data_callback(data, self.serial_port)

    async def start(self):
        """
        Opens the ANT+ channel and begins listening for data.
        """
        self._configure_channel()
        self.node.start()
        self.channel.open()
        logging.info("[ANT+] Channel started and listening for broadcasts.")

        try:
            while True:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.stop()

    def stop(self):
        """
        Closes the channel and stops the ANT+ node.
        """
        logging.info("[ANT+] Shutting down ANT+ receiver.")
        if self.channel:
            self.channel.close()
        self.node.stop()


class TDFBridgeApp:
    """
    The main application class that orchestrates all components: BLE, ANT+, bike control, and logging.
    """

    def __init__(self):
        self.args = self._parse_args()
        self.security = SecurityManager(config_path=CONFIG_PATH)
        self.bike = BikeController(port=self.args.incline)
        self.logger = RideLogger()
        self.ble_service = BLEServiceManager(self.bike, self.security)
        self.processor = SensorDataProcessor(
            bike_controller=self.bike,
            log_file=self.logger.log_path,
            ble_characteristic=None  # Will be set after BLE starts
        )

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="TDF Data Bridge")
        parser.add_argument("--ant", default="usb:0", help="ANT+ device path")
        parser.add_argument("--incline", help="Serial port for incline control")
        parser.add_argument("--ble", action="store_true", help="Enable BLE FTMS broadcasting")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        parser.add_argument("--config", default=CONFIG_PATH, help="Path to config.json")
        parser.add_argument("--test", action="store_true", help="Run in test mode (simulated data, no hardware needed)")
        return parser.parse_args()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.DEBUG if self.args.debug else logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    async def run(self):
        self._setup_logging()

        if not self.security.load_config():
            logging.error("Aborting due to failed security config.")
            return

        if not self.bike.port and not self.args.test:
            logging.error("No serial port detected or provided.")
            return
        elif not self.bike.port and self.args.test:
            logging.warning("[TEST MODE] No serial port detected, continuing in simulation mode.")


        tasks = []

        # Start BLE service if enabled and supported
        if self.args.ble:
            if BleakServer is None:
                logging.error("BLE support not available.")
            elif platform.system() == "Windows":
                logging.error("BLE server not supported on Windows.")
            else:
                tasks.append(asyncio.create_task(self.ble_service.start()))
                # Attach BLE notify characteristic to processor
                self.processor.ble_characteristic = self.ble_service.get_notify_characteristic()

        # Start ANT+ receiver
        if not self.args.test:
            # Start ANT+ receiver only in real mode
            ant_receiver = AntPlusReceiver(
                device_type=FE_C_DEVICE_TYPE,
                serial_port=self.bike.port,
                on_data_callback=self.processor.process
            )
            tasks.append(asyncio.create_task(ant_receiver.start()))
        else:
            # TEST MODE: Simulate data instead of real ANT+ receiver
            tasks.append(asyncio.create_task(self.simulate_ant_plus_data()))


        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logging.info("Interrupted by user. Cleaning up...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def simulate_ant_plus_data(self):
        logging.info("[TEST MODE] Simulating ANT+ data packets.")
        for i in range(10):  # Simulate 10 packets
            fake_data = [0] * 12
            fake_data[7] = random.randint(150, 200)   # Power
            fake_data[8] = 0
            fake_data[10] = random.randint(80, 100)   # Cadence
            fake_data[5] = random.randint(0, 100)     # Grade low byte (0-1%)
            fake_data[6] = 0
            self.processor.process(fake_data)
            await asyncio.sleep(1)  # Simulate time between packets
        logging.info("[TEST MODE] Finished simulating ANT+ data.")


if __name__ == "__main__":
    app = TDFBridgeApp()
    asyncio.run(app.run())