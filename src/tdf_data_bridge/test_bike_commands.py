import unittest
from unittest.mock import patch, MagicMock
import time
from main import BikeController, SensorDataProcessor
from security_utils import (
    is_authorized_mac,
    is_valid_opcode,
    is_throttled,
    init_security_config,
    last_command_time
)

bike = BikeController(port="/dev/ttyUSB0")
processor = SensorDataProcessor(bike_controller=bike)

class TestBikeCommands(unittest.TestCase):

    def setUp(self):
        # Set up known security config before each test
        test_config = {
            "authorized_devices": ["00:11:22:33:44:55"],
            "allowed_opcodes": [0x05],
            "rate_limit_seconds": 1
        }
        init_security_config(test_config)

    @patch("serial.Serial")
    def test_send_incline_valid(self, mock_serial):
        # If using BikeController: bike = BikeController(port="/dev/ttyUSB0"); bike.send_incline(5)
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        bike.send_incline(5)
        mock_instance.write.assert_called_once()

    @patch("serial.Serial")
    def test_send_incline_invalid_range(self, mock_serial):
        bike.send_incline(50) # Invalid incline value
        mock_serial.assert_not_called()

    @patch("serial.Serial")
    def test_send_resistance_command(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        bike.send_resistance(15)      
        mock_instance.write.assert_called_once()

    @patch("serial.Serial")
    def test_send_gear(self, mock_serial):
        mock_instance = MagicMock()
        mock_serial.return_value.__enter__.return_value = mock_instance
        bike.send_gear(2, 5)

        mock_instance.write.assert_called_once()

    def test_estimate_speed_from_cadence(self):
        speed = processor.estimate_speed_from_cadence(90)
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
        last_command_time.clear()
        self.assertFalse(is_throttled(mac))  # First command is allowed
        self.assertTrue(is_throttled(mac))   # Second command should be throttled
        time.sleep(1.1)                      # Wait for cooldown (slightly more than 1 sec)
        self.assertFalse(is_throttled(mac))  # Command allowed after cooldown

if __name__ == '__main__':
    unittest.main()
