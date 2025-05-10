# TDF Data Bridge — Bring Your ProForm Bike to Life on Zwift

Welcome to **TDF Data Bridge**, the project that transforms your **ProForm TDF 5.0** indoor bike into a smart, interactive machine compatible with platforms like **Zwift** and **TrainerRoad**.

Whether you're climbing virtual mountains or logging consistent training indoors, this tool enables real-time control, feedback, and secure BLE communication with your bike.

---

## What It Does

- Serial control of the ProForm bike using a UART (CP2102) USB adapter
- ANT+ data receiver for power, cadence, speed, and grade
- BLE FTMS broadcasting for full compatibility with Zwift and similar apps
- Two-way communication: send incline, resistance, and gear commands to the bike
- Secure BLE Control Point support: MAC address whitelisting, opcode filtering, and rate limiting
- CSV-based ride data logging

---

## BLE Security Features

The `on_write()` BLE handler includes:

- MAC address filtering (whitelist only)
- Opcode validation to allow only recognized FTMS commands
- Rate limiting to prevent excessive BLE writes from a single device

To enable this handler in your BLE setup:
```python
control_point_characteristic.set_write_callback(on_write)
```

---

## Requirements

### Hardware
- ProForm TDF 5.0 Bike
- ANT+ USB stick (Garmin, CooSpo, etc.)
- UART USB to TTL adapter (CP2102 preferred)
- 4-pin JST-PH to female Dupont cable

### Software
- Python 3.8+
- Install required libraries:
```bash
pip install -r requirements.txt
```

---

## How to Run

```bash
python main.py --ble --incline /dev/ttyUSB0 --debug
```

### Command-Line Flags
- `--ble`: Start the FTMS BLE service
- `--incline`: Serial port path connected to the bike
- `--debug`: Enable debug logging
- `--ant`: ANT+ USB device path (default: `usb:0`)

---

## Testing

Run unit tests with:
```bash
python -m unittest test_bike_commands.py
```
Covers:
- Incline/resistance commands
- Gear shifting
- BLE MAC whitelist, opcode validation, and throttle enforcement

---

## Project Structure

```
.
├── main.py                    # Main application logic
├── test_bike_commands.py     # Unit tests
├── ride_log.csv              # Auto-generated ride data log
├── requirements.txt          # Dependency list
└── README.md                 # Project description
```

---

## Planned Improvements

- Web dashboard (Flask/React) for live performance data
- Bluetooth auto-pairing and bonding
- Configurable settings for trusted devices and ANT+ sources

---

## Credits

Developed with the help of:
- [OpenANT](https://github.com/Tigge/openant)
- [Bleak](https://github.com/hbldh/bleak)
- [Zwift Insider](https://zwiftinsider.com/) for guidance on FTMS specs

---

## License

MIT License © 2025