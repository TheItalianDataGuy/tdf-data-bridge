import time

# Global variables to hold security settings
# These will be initialized at runtime using values from config.json
AUTHORIZED_DEVICES = set()        # Stores allowed BLE MAC addresses
ALLOWED_OPCODES = set()           # Stores allowed BLE opcodes
RATE_LIMIT_SECONDS = 1.5          # Cooldown period between allowed commands per device
last_command_time = {}            # Tracks the last time a device sent a command


def init_security_config(config):
    """
    Initializes security configuration from a dictionary (typically loaded from config.json).

    Args:
        config (dict): Should contain:
            - "authorized_devices": List of allowed MAC addresses (strings)
            - "allowed_opcodes": List of allowed operation codes (integers)
            - "rate_limit_seconds": Optional float for throttling window
    """
    global AUTHORIZED_DEVICES, ALLOWED_OPCODES, RATE_LIMIT_SECONDS

    # Populate security parameters from config or use defaults
    AUTHORIZED_DEVICES = set(config.get("authorized_devices", []))
    ALLOWED_OPCODES = set(config.get("allowed_opcodes", []))
    RATE_LIMIT_SECONDS = config.get("rate_limit_seconds", 1.5)

    # Clear existing command timestamps to avoid conflicts with new config
    last_command_time.clear()


def is_authorized_mac(mac_address):
    """
    Checks whether a BLE device's MAC address is allowed.

    Args:
        mac_address (str): MAC address of the BLE device.

    Returns:
        bool: True if authorized, False otherwise.
    """
    return mac_address in AUTHORIZED_DEVICES


def is_valid_opcode(opcode):
    """
    Checks whether the provided opcode is supported.

    Args:
        opcode (int): BLE operation code from the client.

    Returns:
        bool: True if allowed, False otherwise.
    """
    return opcode in ALLOWED_OPCODES


def is_throttled(mac):
    """
    Implements rate limiting per device.

    Args:
        mac (str): MAC address of the sending device.

    Returns:
        bool: True if the device is sending commands too frequently, False otherwise.
    """
    now = time.time()

    # Check if the device has sent a command recently
    if mac in last_command_time and now - last_command_time[mac] < RATE_LIMIT_SECONDS:
        return True

    # Update last command time
    last_command_time[mac] = now
    return False
