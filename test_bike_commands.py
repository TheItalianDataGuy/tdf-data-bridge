import unittest
from unittest.mock import patch, MagicMock
import time

from tdf_data_bridge import (
    send_incline_command,
    send_resistance_command,
    send_gear,
    estimate_speed_from_cadence
)

# BLE security enhancements
AUTHORIZED_DEVICES = {"00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"}
ALLOWED_OPCODES = {0x05, 0x30, 0x40}
last_command_time = {}

def is_authorized_mac(mac_address):
    return mac_address in AUTHORIZED_DEVICES

def is_valid_opcode(opcode):
    return opcode in ALLOWED_OPCODES

def is_throttled(mac, cooldown=1.5):
    now = time.time()
    if mac in last_command_time and now - last_command_time[mac] < cooldown:
        return True
    last_command_time[mac] = now
    return False

class TestBikeCommands(unittest.TestCase):

    @patch("serial.Serial")
    def test_send_incline_valid(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_incline_command(5, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    @patch("serial.Serial")
    def test_send_incline_invalid_range(self, mock_serial):
        send_incline_command(50, "/dev/ttyUSB0")  # Out of range
        mock_serial.assert_not_called()

    @patch("serial.Serial")
    def test_send_resistance_command(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_resistance_command(15, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    @patch("serial.Serial")
    def test_send_gear(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_gear(2, 5, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    def test_estimate_speed_from_cadence(self):
        speed = estimate_speed_from_cadence(90)  # Typical cadence
        self.assertGreater(speed, 0)
        self.assertIsInstance(speed, float)

    def test_mac_authorization(self):
        self.assertTrue(is_authorized_mac("00:11:22:33:44:55"))
        self.assertFalse(is_authorized_mac("DE:AD:BE:EF:00:00"))

    def test_opcode_validation(self):
        self.assertTrue(is_valid_opcode(0x05))
        self.assertFalse(is_valid_opcode(0x99))

    def test_reject_invalid_mac(self):
        device = MagicMock()
        device.address = "DE:AD:BE:EF:00:00"
        data = bytearray([0x05, 10])
        result = "rejected" if not is_authorized_mac(device.address) else "accepted"
        self.assertEqual(result, "rejected")

    def test_reject_invalid_opcode(self):
        data = bytearray([0x99, 1])
        result = "rejected" if not is_valid_opcode(data[0]) else "accepted"
        self.assertEqual(result, "rejected")

    def test_ble_command_rate_limit(self):
        mac = "00:11:22:33:44:55"
        self.assertFalse(is_throttled(mac))  # first command
        self.assertTrue(is_throttled(mac))   # second command too soon
        time.sleep(2)
        self.assertFalse(is_throttled(mac))  # after cooldown

if __name__ == '__main__':
    unittest.main()
