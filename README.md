# TDF Data Bridge

Control your **ProForm TDF 5.0** indoor bike using **Zwift**, **ANT+**, and **BLE FTMS**. This bridge allows automatic incline, resistance, and gear control while securely exposing data over Bluetooth and logging ride metrics locally.

---

## 🚴‍♂️ Features

- Control incline, resistance, and gear via serial commands
- Read real-time data from ANT+ FE-C broadcasts
- Broadcast metrics to BLE FTMS-compatible apps (e.g., Zwift)
- Secure BLE control: MAC whitelist, opcode filtering, rate limiting
- Automatically logs rides to CSV (`ride_log.csv`)
- CLI tool installed via `tdf-bridge` command

---

## 🔧 Installation

Install using `pip` with the new [`pyproject.toml`](https://peps.python.org/pep-0621/) standard:

```bash
pip install .
```

Or build a wheel:

```bash
pip install build
python -m build
```

Then install the `.whl` file from `dist/`.

---

## 💻 Usage

```bash
tdf-bridge --ble --incline /dev/ttyUSB0 --debug
```

### CLI Options
- `--ble`: Enable BLE FTMS broadcasting
- `--incline`: Set serial port path manually (optional)
- `--ant`: Set ANT+ USB device (default: `usb:0`)
- `--debug`: Enable detailed logs

---

## 🔐 Security

- BLE writes only accepted from approved MAC addresses
- Only specific FTMS opcodes allowed
- Commands rate-limited (configurable)

Security settings are defined in `config.json`:

```json
{
  "authorized_devices": ["AA:BB:CC:DD:EE:FF"],
  "allowed_opcodes": [5, 48, 64],
  "rate_limit_seconds": 1.5
}
```

---

## 📁 Project Structure

```
.
├── tdf_data_bridge/           # Main module
├── security_utils.py          # BLE security checks
├── ride_log.csv               # Generated ride log
├── config.json                # Security settings
├── requirements.txt
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## 🛠 Development

Run locally:

```bash
python tdf_data_bridge/main.py --debug --ble
```

Test with mock BLE devices or ANT+ emulator if needed.

---

## 📜 License

[MIT License](LICENSE)

---

## 🌐 Author

[TheItalianDataGuy](https://github.com/TheItalianDataGuy)