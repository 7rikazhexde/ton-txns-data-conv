import os
import sys

from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError
from tomlkit.toml_file import TOMLFile

# Load configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, "config.toml")

if not os.path.exists(config_file_path):
    print(f"Error: Configuration file not found at {config_file_path}.")
    sys.exit(1)

try:
    toml_config = TOMLFile(config_file_path)
    config = toml_config.read()
except Exception as e:
    print(f"Error: Failed to read configuration file. {str(e)}")
    sys.exit(1)

# TON Address Info
DEFAULT_UF_ADDRESS = config.get("ton_info", {}).get("user_friendly_address", "")

if not DEFAULT_UF_ADDRESS:
    print("Error: Please set 'user_friendly_address' in the config.toml file.")
    sys.exit(1)

try:
    address = Address(DEFAULT_UF_ADDRESS)
except AddressError as e:
    print(f"Error: Invalid user_friendly_address. {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"Error: An unexpected error occurred while creating the address. {str(e)}")
    sys.exit(1)

try:
    # to_str() arguments: is_user_friendly, is_url_safe, is_bounceable, is_test_only
    print(
        "User-friendly, Bounceable, URL-safe, Not test-only:",
        address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=True,
            is_test_only=False,
        ),
    )
    print(
        "User-friendly, Bounceable, Not URL-safe, Not test-only:",
        address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=False,
            is_test_only=False,
        ),
    )
    print(
        "User-friendly, Not Bounceable, URL-safe, Not test-only:",
        address.to_str(
            is_user_friendly=True,
            is_bounceable=False,
            is_url_safe=True,
            is_test_only=False,
        ),
    )
    print(
        "User-friendly, Bounceable, URL-safe, Test-only:",
        address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=True,
            is_test_only=True,
        ),
    )
    print(
        "User-friendly, Not Bounceable, URL-safe, Test-only:",
        address.to_str(
            is_user_friendly=True,
            is_bounceable=False,
            is_url_safe=True,
            is_test_only=True,
        ),
    )
except AddressError as e:
    print(f"Error: Failed to convert address to string. {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"Error: An unexpected error occurred while processing the address. {str(e)}")
    sys.exit(1)
