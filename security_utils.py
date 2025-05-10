import time
import json

with open("config.json") as f:
    config = json.load(f)

AUTHORIZED_DEVICES = set(config["authorized_devices"])
ALLOWED_OPCODES = set(config["allowed_opcodes"])
RATE_LIMIT_SECONDS = config["rate_limit_seconds"]

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