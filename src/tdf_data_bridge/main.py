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
import platform

from security_utils import (
    is_authorized_mac,
    is_valid_opcode,
    is_throttled,
    init_security_config,
)

class BikeController:
    """
    Handles serial communication with the ProForm TDF bike for incline, resistance, and gear control.
    """

    def __init__(self, port=None):
        self.port = port or self.auto_detect_serial_port()
        self.last_sent_incline = None

    def auto_detect_serial_port(self):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if "SLAB" in port.description or "CP210" in port.description:
                logging.info(f"[BikeController] Auto-detected serial port: {port.device}")
                return port.device
        logging.warning("[BikeController] No compatible serial port detected.")
        return None

    def send_incline(self, grade):
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
        if self.port is None:
            return
        cmd = f"R{level:02d}\r\n".encode("ascii")
        self._write_to_bike(cmd, "[Resistance]")

    def send_gear(self, front, rear):
        if self.port is None:
            return
        cmd = f"G{front}{rear}\r\n".encode("ascii")
        self._write_to_bike(cmd, "[Gear]")

    def _write_to_bike(self, command, label=""):
        try:
            with serial.Serial(self.port, 115200, timeout=1, exclusive=True) as ser:
                ser.write(command)
                logging.debug(f"{label} Sent: {command}")
        except serial.SerialException as e:
            logging.error(f"{label} Serial error: {e}")

class SensorDataProcessor:
    """
    Processes incoming ANT+ data, logs metrics, and commands the bike.
    """

    def __init__(self, bike_controller, log_file="ride_log.csv"):
        self.bike = bike_controller
        self.log_file = log_file
        self.current_resistance = 10
        self.current_incline = 0.0
        self.current_gear = (1, 1)

        # Create log file with header if it doesn't exist
        if not os.path.exists(log_file):
            with open(log_file, "w", newline="") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["timestamp", "power", "cadence", "speed", "incline"])

    def estimate_speed_from_cadence(self, cadence, gear_ratio=2.5):
        return round(cadence * gear_ratio / 60.0 * 3.6, 1)

    def process(self, data, *args):
        """
        Called on each ANT+ data packet. Parses and logs metrics, controls the bike.
        """
        # Modify these indices based on the actual FE-C profile
        print("RAW ANT+ DATA:", list(data))
        try:
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
        except Exception as e:
            logging.error(f"[SensorDataProcessor] Error processing data: {e}")

    def _map_grade(self, percent_grade):
        if percent_grade < 0:
            return percent_grade * 0.5
        elif percent_grade > 10:
            return 10 + (percent_grade - 10) * 0.3
        else:
            return percent_grade

    def _log_to_csv(self, power, cadence, speed, incline):
        with open(self.log_file, "a", newline="") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([time.time(), power, cadence, speed, incline])

class SecurityManager:
    """
    Wraps security checks for MAC address validation, opcode filtering, and rate limiting.
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.initialized = False

    def load_config(self):
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
        if not os.path.exists(self.log_path):
            try:
                with open(self.log_path, "w", newline="") as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(["timestamp", "power", "cadence", "speed", "incline"])
                logging.info(f"[LOGGER] Created new ride log at: {self.log_path}")
            except Exception as e:
                logging.error(f"[LOGGER] Failed to create log file: {e}")

    def log(self, power: int, cadence: int, speed: float, incline: float):
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
        self.channel = self.node.new_channel(Channel.Type.BIDIRECTIONAL_RECEIVE)
        self.channel.set_period(8182)
        self.channel.set_search_timeout(255)
        self.channel.set_rf_freq(57)
        self.channel.set_id(0, self.device_type, 0)
        self.channel.on_broadcast_data = lambda data: self.on_data_callback(data, self.serial_port)

    async def start(self):
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
        logging.info("[ANT+] Shutting down ANT+ receiver.")
        if self.channel:
            self.channel.close()
        self.node.stop()

FE_C_DEVICE_TYPE = 17  # Device type for FE-C (Fitness Equipment Control) devices

class TDFBridgeApp:
    """
    The main application class that orchestrates all components: ANT+, bike control, and logging.
    """

    def __init__(self):
        self.args = self._parse_args()
        self.security = SecurityManager(config_path=self.args.config)
        self.bike = BikeController(port=self.args.incline)
        self.logger = RideLogger()
        self.processor = SensorDataProcessor(
            bike_controller=self.bike,
            log_file=self.logger.log_path
        )

    def _parse_args(self):
        parser = argparse.ArgumentParser(description="TDF Data Bridge")
        parser.add_argument("--ant", default="usb:0", help="ANT+ device path")
        parser.add_argument("--incline", help="Serial port for incline control")
        parser.add_argument("--debug", action="store_true", help="Enable debug logging")
        parser.add_argument("--config", default="config.json", help="Path to config.json")
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

        if not self.bike.port:
            logging.error("No serial port detected or provided.")
            return

        tasks = []

        # Start ANT+ receiver
        ant_receiver = AntPlusReceiver(
            device_type=FE_C_DEVICE_TYPE,
            serial_port=self.bike.port,
            on_data_callback=self.processor.process
        )
        tasks.append(asyncio.create_task(ant_receiver.start()))

        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            logging.info("Interrupted by user. Cleaning up...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

if __name__ == "__main__":
    app = TDFBridgeApp()
    asyncio.run(app.run())
