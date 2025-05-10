import unittest
from unittest.mock import patch, MagicMock
import time
from security_utils import is_authorized_mac, is_valid_opcode, is_throttled
from main import (
    send_incline_command,
    send_resistance_command,
    send_gear,
    estimate_speed_from_cadence
)

# Test suite for the TDF bike command utilities and security checks
class TestBikeCommands(unittest.TestCase):

    # Test sending a valid incline command
    @patch("serial.Serial")
    def test_send_incline_valid(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_incline_command(5, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    # Test sending an incline command that is out of valid range
    @patch("serial.Serial")
    def test_send_incline_invalid_range(self, mock_serial):
        send_incline_command(50, "/dev/ttyUSB0")  # Invalid incline value
        mock_serial.assert_not_called()

    # Test sending a resistance command
    @patch("serial.Serial")
    def test_send_resistance_command(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_resistance_command(15, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    # Test sending a gear shift command
    @patch("serial.Serial")
    def test_send_gear(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        send_gear(2, 5, "/dev/ttyUSB0")
        mock_instance.write.assert_called_once()

    # Test speed estimation from cadence
    def test_estimate_speed_from_cadence(self):
        speed = estimate_speed_from_cadence(90)  # Typical cadence
        self.assertGreater(speed, 0)
        self.assertIsInstance(speed, float)

    # Test if a known MAC address is authorized
    def test_mac_authorization(self):
        self.assertTrue(is_authorized_mac("00:11:22:33:44:55"))
        self.assertFalse(is_authorized_mac("DE:AD:BE:EF:00:00"))

    # Test if a known opcode is valid
    def test_opcode_validation(self):
        self.assertTrue(is_valid_opcode(0x05))
        self.assertFalse(is_valid_opcode(0x99))

    # Test rejection of an unauthorized MAC address
    def test_reject_invalid_mac(self):
        device = MagicMock()
        device.address = "DE:AD:BE:EF:00:00"
        data = bytearray([0x05, 10])
        result = "rejected" if not is_authorized_mac(device.address) else "accepted"
        self.assertEqual(result, "rejected")

    # Test rejection of an invalid opcode
    def test_reject_invalid_opcode(self):
        data = bytearray([0x99, 1])
        result = "rejected" if not is_valid_opcode(data[0]) else "accepted"
        self.assertEqual(result, "rejected")

    # Test that commands from the same MAC address are throttled appropriately
    def test_ble_command_rate_limit(self):
        mac = "00:11:22:33:44:55"
        self.assertFalse(is_throttled(mac))  # First command is allowed
        self.assertTrue(is_throttled(mac))   # Second command should be throttled
        time.sleep(2)                        # Wait for cooldown
        self.assertFalse(is_throttled(mac))  # Command allowed after cooldown

if __name__ == '__main__':
    unittest.main()
