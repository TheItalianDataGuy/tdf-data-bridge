import time

AUTHORIZED_DEVICES = {"00:11:22:33:44:55", "AA:BB:CC:DD:EE:FF"}
ALLOWED_OPCODES = {0x05, 0x30, 0x40}
last_command_time = {}

def is_authorized_mac(mac_address):
    """Check if the BLE device MAC address is in the authorized list."""
    return mac_address in AUTHORIZED_DEVICES

def is_valid_opcode(opcode):
    """Verify that the received opcode is supported."""
    return opcode in ALLOWED_OPCODES

def is_throttled(mac, cooldown=1.5):
    """Limit how often commands can be sent from the same MAC address."""
    now = time.time()
    if mac in last_command_time and now - last_command_time[mac] < cooldown:
        return True
    last_command_time[mac] = now
    return False