import sys
from pathlib import Path
from typing import Any, Dict

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError

from ton_txns_data_conv.utils.config_loader import load_config


def get_address_variations(address: Address) -> Dict[str, str]:
    """
    指定されたアドレスの異なるバリエーションを生成する

    :param address: Addressオブジェクト
    :return: アドレスの異なるバリエーションを含む辞書
    """
    return {
        "User-friendly, Bounceable, URL-safe, Not test-only": address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=True,
            is_test_only=False,
        ),
        "User-friendly, Bounceable, Not URL-safe, Not test-only": address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=False,
            is_test_only=False,
        ),
        "User-friendly, Not Bounceable, URL-safe, Not test-only": address.to_str(
            is_user_friendly=True,
            is_bounceable=False,
            is_url_safe=True,
            is_test_only=False,
        ),
        "User-friendly, Bounceable, URL-safe, Test-only": address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=True,
            is_test_only=True,
        ),
        "User-friendly, Not Bounceable, URL-safe, Test-only": address.to_str(
            is_user_friendly=True,
            is_bounceable=False,
            is_url_safe=True,
            is_test_only=True,
        ),
    }


def main() -> None:
    """
    メイン関数。設定を読み込み、アドレスを処理し、結果を出力する。
    """
    config: Dict[str, Any] = load_config()
    default_uf_address: str = config.get("ton_info", {}).get(
        "user_friendly_address", ""
    )

    if not default_uf_address:
        print("Error: Please set 'user_friendly_address' in the config.toml file.")
        sys.exit(1)

    try:
        address = Address(default_uf_address)
        address_variations = get_address_variations(address)
        for description, addr in address_variations.items():
            print(f"{description}:", addr)
    except AddressError as e:
        print(f"Error: Invalid user_friendly_address. {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(
            f"Error: An unexpected error occurred while processing the address. {str(e)}"
        )
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
