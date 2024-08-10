import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError

from ton_txns_data_conv.utils.config_loader import load_config

config = load_config()

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
