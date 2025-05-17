# TDF Data Bridge

![Python Tests](https://github.com/TheItalianDataGuy/tdf-data-bridge/actions/workflows/python-tests.yml/badge.svg?branch=ble-version)

![Python Version](https://img.shields.io/badge/python-3.9%20|%203.10%20|%203.11-blue)

[![CodeQL](https://github.com/TheItalianDataGuy/tdf-data-bridge/actions/workflows/codeql-analysis.yml/badge.svg?branch=ble-version)](https://github.com/TheItalianDataGuy/tdf-data-bridge/actions/workflows/codeql-analysis.yml)

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

Control your **ProForm TDF 5.0** indoor bike using **Zwift**, **ANT+**, and **BLE FTMS** protocols.  
This bridge enables automatic incline, resistance, and gear control while securely exposing live data over Bluetooth and logging ride metrics locally.

---

## 🚴‍♂️ Features

- **Automatic incline, resistance, and gear control** via serial commands
- **Real-time data ingestion** from ANT+ FE-C broadcasts (Fitness Equipment Control)
- **BLE FTMS (Fitness Machine Service) notifications** for compatible apps (e.g., Zwift, TrainerRoad)
- **Configurable security**: MAC whitelist, opcode filtering, and rate limiting for BLE control
- **Ride logging**: All metrics saved to CSV (`ride_log.csv`)
- **Test mode**: Simulate ride data for demo and development (no hardware required)
- **Modern Python project structure** for easy extension and testing

---

## 🔧 Installation

Clone the repository and install using [PEP 621](https://peps.python.org/pep-0621/) standards:

```bash
git clone https://github.com/TheItalianDataGuy/tdf-data-bridge.git
cd tdf-data-bridge
pip install .
```

Or build a wheel:

```bash
pip install build
python -m build
pip install dist/tdf_data_bridge-*.whl
```

---

## 💻 Usage

Run the bridge from the project root:

```bash
python src/tdf_data_bridge/main.py --ble --incline /dev/ttyUSB0 --debug
```

### **CLI Options**

| Flag           | Description                                                 |
| -------------- | ----------------------------------------------------------- |
| `--ble`        | Enable BLE FTMS broadcasting (see platform support below)   |
| `--incline`    | Set serial port path manually (optional, auto-detects by default) |
| `--ant`        | Set ANT+ USB device path (default: `usb:0`)                |
| `--debug`      | Enable verbose debug logging                                |
| `--config`     | Path to security config file (default: `config.json`)       |
| `--test`       | **Simulate ride data with no hardware required**            |

---

### **Test Mode Example**

To simulate the entire workflow without any hardware (for portfolio/demo):

```bash
python src/tdf_data_bridge/main.py --ble --test --debug
```

- This will generate and process fake ride data, printing simulated BLE FTMS packets in the log for easy demonstration.

---

## ⚠️ Platform Support & BLE Limitations

- **ANT+ and Serial support:**  
  - Works on all major platforms (Linux, macOS, Windows) with compatible hardware.
- **BLE FTMS server:**  
  - **Linux**: BLE FTMS server mode supported with [bleak](https://github.com/hbldh/bleak) or [aiobleserver](https://github.com/JennyMish/aiobleserver).
  - **macOS/Windows**:  
    - Python BLE server is **not available** due to OS and library limitations (see [issue](https://github.com/hbldh/bleak/issues/1230)).
    - BLE FTMS code will log simulated notifications, but cannot advertise as a peripheral/server.
    - This does **not** affect test mode or portfolio review; simulated BLE notifications will still be shown in the logs.

---

## 🔐 Security

- BLE control is restricted by a whitelist of allowed MAC addresses
- Only valid FTMS opcodes are accepted (as configured)
- All BLE commands are rate-limited to prevent abuse

Example `config.json`:

```json
{
  "authorized_devices": ["AA:BB:CC:DD:EE:FF"],
  "allowed_opcodes": [5, 48, 64],
  "rate_limit_seconds": 1.5
}
```

---

## 🔑 Permissions

- **Serial Port:**  
  On Linux, add your user to the `dialout` group:  
  ```bash
  sudo usermod -aG dialout $USER
  ```

- **BLE:**  
  On Linux, add your user to the `bluetooth` group:  
  ```bash
  sudo usermod -aG bluetooth $USER
  ```
  On macOS, no special permissions are usually required.

- **Do NOT run as root** unless absolutely necessary.

---

## 📁 Project Structure

```
.
├── src/
│   └── tdf_data_bridge/
│       ├── main.py                 # Main entry point
│       ├── security_utils.py       # BLE security logic
│       ├── test_bike_commands.py   # Serial/command tests
│       └── __init__.py             # Package init
├── ride_log.csv                    # Ride log (generated)
├── config.json                     # Security config
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 🛠 Development

- Develop locally with or without hardware using `--test` mode.
- Simulated BLE/ANT+ logs are printed for easy debugging and demonstration.
- Code follows modern Python best practices for modularity and testability.

---

## 🛡 Dependency Security

- Check for vulnerabilities with:
  ```bash
  pip install pip-audit
  pip-audit
  ```
- Update dependencies regularly and review release notes for security patches.

---

## 🧪 Testing

- All core logic for command transmission and BLE security is covered by automated unit tests using Python's `unittest` framework.
- To run all tests, execute:
  ```bash
  python -m unittest discover src/tdf_data_bridge
  ```
  or run a specific test file directly:
  ```bash
  python src/tdf_data_bridge/test_bike_commands.py
  ```
- Tests use mocks and do **not** require connected hardware for validation.
- Integrate with GitHub Actions or your preferred CI tool for continuous testing and professional code validation.

---

## 🧪 Example: Simulated BLE FTMS Packet Log Output

```
[BLE Notify FTMS] Sent: [255, 3, 120, 44, 180, 0, 98, 0, 150, ...]
```
> When running in test mode, this is printed/logged to demonstrate BLE notification content (even on platforms that do not support BLE server).

---

## 📜 License

[MIT License](LICENSE)

---

## 🌐 Author

[TheItalianDataGuy](https://github.com/TheItalianDataGuy)

---

**Issues?**  
Please open an issue or contact me via GitHub!