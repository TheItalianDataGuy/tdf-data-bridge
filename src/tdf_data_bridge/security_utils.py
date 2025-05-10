import time

# These will be set dynamically at runtime
AUTHORIZED_DEVICES = set()
ALLOWED_OPCODES = set()
RATE_LIMIT_SECONDS = 1.5
last_command_time = {}

def init_security_config(config):
    """Initialize security settings from a config dictionary."""
    global AUTHORIZED_DEVICES, ALLOWED_OPCODES, RATE_LIMIT_SECONDS
    AUTHORIZED_DEVICES = set(config.get("authorized_devices", []))
    ALLOWED_OPCODES = set(config.get("allowed_opcodes", []))
    RATE_LIMIT_SECONDS = config.get("rate_limit_seconds", 1.5)
    last_command_time.clear()

def is_authorized_mac(mac_address):
    """Check if the BLE device MAC address is in the authorized list."""
    return mac_address in AUTHORIZED_DEVICES

def is_valid_opcode(opcode):
    """Verify that the received opcode is supported."""
    return opcode in ALLOWED_OPCODES

def is_throttled(mac):
    """Limit how often commands can be sent from the same MAC address."""
    now = time.time()
    if mac in last_command_time and now - last_command_time[mac] < RATE_LIMIT_SECONDS:
        return True
    last_command_time[mac] = now
    return False