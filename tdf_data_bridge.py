import serial
import argparse
from openant.easy.node import Node
from openant.easy.channel import Channel
from openant.base.constants import DeviceType

try:
    from bleak import BleakServer  # Optional BLE support (Linux/macOS only)
except ImportError:
    BleakServer = None

# Function to send incline commands to the bike
# Accepts a grade between -10 and +20, formats it as a command string like 'G+05\r\n'
def send_incline_command(grade, serial_port):
    if not (-10 <= grade <= 20):  # Limit check for supported incline range
        return
    sign = '+' if grade >= 0 else '-'  # Determine + or - sign
    value = f"{abs(int(round(grade))):02d}"  # Format the absolute value with leading zero (e.g. '05')
    cmd = f"G{sign}{value}\r\n".encode("ascii")  # Final command string (e.g. G+05\r\n)
    with serial.Serial(serial_port, 115200, timeout=1) as ser:  # Open serial connection
        ser.write(cmd)  # Send command to bike

# Callback function triggered when ANT+ data is received from the bike
# Extracts power and cadence and prints them, then sends a test incline command
def on_data(data, serial_port):
    power = data[7] | (data[8] << 8)  # Extract power value (2 bytes, little endian)
    cadence = data[10]  # Extract cadence from byte 10
    print(f"Power: {power} W, Cadence: {cadence} rpm")
    send_incline_command(5, serial_port)  # Simulate a 5% incline (can be replaced with real logic)

# Placeholder BLE FTMS service setup (actual implementation is platform-dependent)
def start_ble_ftms():
    if BleakServer is None:
        print("BLE not supported or bleak not installed.")
        return
    print("[BLE] FTMS service would start here (implementation pending).")

# Main setup for ANT+ communication with the bike
# Creates a node and channel, sets the frequency, device type, and binds the data callback
def main():
    parser = argparse.ArgumentParser(description="TDF Data Bridge")
    parser.add_argument("--ant", default="usb:0", help="ANT+ device path (e.g., usb:0)")
    parser.add_argument("--incline", default="/dev/tty.SLAB_USBtoUART", help="Serial port for incline control")
    parser.add_argument("--ble", action="store_true", help="Enable BLE FTMS broadcasting")
    args = parser.parse_args()

    if args.ble:
        start_ble_ftms()  # Optional BLE functionality (placeholder)

    node = Node()
    network = node.get_free_network()
    network.set_key(0xB9, [0]*8)  # ANT+ network key (public key)

    channel = node.new_channel(Channel.Type.BIDIRECTIONAL_RECEIVE)
    channel.set_period(8182)  # Data transmission frequency (4 Hz)
    channel.set_search_timeout(255)  # How long it searches before timing out (255 = always)
    channel.set_rf_freq(57)  # ANT+ frequency (2457 MHz)
    channel.set_id(0, 0, 0)  # Wildcard device ID
    channel.set_device_type(DeviceType.FE_C)  # Device type for smart trainers (Fitness Equipment Control)

    # Bind the callback with serial port context using a lambda
    channel.on_broadcast_data = lambda data: on_data(data, args.incline)

    node.start()  # Start ANT+ communication
    channel.open()  # Open the channel

    try:
        while True:
            pass  # Keeps the script running
    except KeyboardInterrupt:
        print("Stopped.")
        channel.close()  # Close the ANT+ channel
        node.stop()  # Stop the ANT+ node

# Run the script if executed directly
if __name__ == "__main__":
    main()
