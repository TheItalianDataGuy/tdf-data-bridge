# TDF Data Bridge — Bring Your ProForm Bike to Life on Zwift

This project enables your ProForm TDF 5.0 indoor bike to communicate with platforms like Zwift using ANT+ and BLE FTMS. It offers real-time control for incline, resistance, and gear, and supports secure BLE communication and data logging.

---

## Features

- Serial control of the ProForm bike via USB UART (CP2102)
- ANT+ FE-C data receiver for power, cadence, speed, and grade
- BLE FTMS broadcasting (speed, cadence, power, incline, gear)
- Secure BLE Control Point:
  - MAC address whitelist
  - Opcode validation
  - Rate limiting
- Robust error handling for BLE communication
- Timestamped CSV ride logging

---

## Requirements

### Hardware
- ProForm TDF 5.0 Bike
- ANT+ USB Stick (e.g. Garmin, CooSpo)
- CP2102 USB to TTL adapter (3.3V logic)
- 4-pin JST-PH to Female Dupont cable

### Software
- Python 3.8+
- Required libraries:
```bash
pip install -r requirements.txt
```

---

## Usage

Run the bridge:

```bash
python main.py --ble --incline /dev/ttyUSB0 --debug
```

### Flags
- `--ble`: Enable BLE FTMS broadcasting
- `--incline`: Serial port path (e.g., `/dev/ttyUSB0` or `COM3`)
- `--debug`: Enable detailed logging
- `--ant`: Path to ANT+ USB device (default: `usb:0`)

---

## Security

BLE control is protected by:
- MAC address whitelist (see `security_utils.py`)
- Allowed FTMS opcodes only
- Command rate limiting (default: 1.5s)

All unexpected BLE data is safely rejected and logged.

---

## Project Structure

```
.
├── main.py                    # Core application logic
├── security_utils.py          # BLE MAC whitelist, opcode checks, rate limiting
├── test_bike_commands.py      # Unit tests
├── requirements.txt           # Python dependencies
├── ride_log.csv               # Generated session logs
└── README.md                  # This file
```

---

## Future Improvements

- Web dashboard for live telemetry
- Config file for trusted MACs and settings
- Unit tests for BLE security and ANT+ parsing

---

## License

MIT License © 2025