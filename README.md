# 🌀 TDF Data Bridge

> Control your ProForm TDF bike using ANT+ and BLE FTMS — now with resistance, incline, ERG mode, and gear simulation.

---

## 🚴 Overview

This project bridges **ANT+ FE-C** data (e.g. from Zwift or TrainerRoad) with **ProForm TDF bikes** via USB serial. It interprets real-time cycling data and sends precise incline, resistance, and gear commands to your bike.

It also supports **BLE FTMS broadcasting** so BLE-only devices (like iPads or Apple TV) can receive indoor bike data and control the trainer wirelessly.

---

## 💡 Features

- ✅ ANT+ FE-C listener for Zwift, Rouvy, TrainerRoad, etc.
- ✅ BLE FTMS-compatible GATT service
- ✅ Real-time incline adjustment
- ✅ Resistance / ERG mode control
- ✅ Gear simulation (front + rear)
- ✅ BLE control point command handling
- ✅ Power, speed, cadence, incline, and gear notifications
- ✅ Auto-logging to CSV for post-ride analysis

---

## 🔧 Hardware Requirements

- ProForm TDF 5.0 (or similar ICON-based bike)
- USB-TTL adapter (e.g. CP2102)
- Pre-crimped 4-pin JST-PH to Dupont cable
- ANT+ USB dongle
- Optional: BLE host device (Linux/macOS)

---

## ⚙️ Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/tdf-data-bridge.git
   cd tdf-data-bridge
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Connect bike via USB-TTL (JST-PH cable)**

4. **Run the script**:

   **ANT+ only**:
   ```bash
   python tdf_data_bridge.py --ant usb:0 --incline /dev/tty.SLAB_USBtoUART
   ```

   **With BLE FTMS support**:
   ```bash
   python tdf_data_bridge.py --ant usb:0 --incline /dev/tty.SLAB_USBtoUART --ble
   ```

   Add `--debug` for verbose logging.

---

## 📡 ANT+ and BLE Control

| Protocol | Input           | Output                     |
|----------|------------------|-----------------------------|
| ANT+     | Zwift, TrainerRoad | Bike: Incline & ERG        |
| BLE FTMS | Companion App      | Broadcast metrics + control|

Supports opcodes:
- `0x05`: Set target incline
- `0x30`: Set resistance level
- `0x40`: Simulated gear change (front/rear)

---

## 📊 Logged Data

All rides are logged to `ride_log.csv` with:
- Timestamp
- Power (W)
- Cadence (RPM)
- Speed (km/h)
- Incline (%)

---

## 🧪 Testing

Use [nRF Connect](https://www.nordicsemi.com/Products/Development-tools/nRF-Connect-for-desktop) to test the FTMS GATT service.

---

## 🛠 Roadmap

- [ ] Add FTMS response opcodes for control confirmations
- [ ] Implement speed simulation via virtual flywheel
- [ ] Graphical dashboard (e.g. using Dash or Streamlit)

---

## 📄 License

MIT License © 2025 [Your Name]

---

## 🙌 Acknowledgements

Built with ❤️ for cyclists, hackers, and open source lovers.
