import datetime
import json
import os
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Union, cast

import requests
from pytonapi import Tonapi
from pytonapi.schema.blockchain import Transaction
from tomlkit.toml_file import TOMLFile


def nano_to_amount(value: int, precision: int = 9) -> float:
    """Converts a value from nanoton to TON without rounding.

    Args:
        value (int): The value to convert, in nanoton. This should be a positive integer.
        precision (int, optional): The number of decimal places to include in the converted value. Defaults to 9.

    Returns:
        float: The converted value in TON.

    Raises:
        ValueError: If the value is not a positive integer or the precision is not a non-negative integer.
    """
    if not isinstance(value, int) or value < 0:
        raise ValueError("Value must be a positive integer.")

    if not isinstance(precision, int) or precision < 0:
        raise ValueError("Precision must be a non-negative integer.")

    result: float = value / (10**precision)
    return result


def convert_to_dict(
    obj: Union[List[Transaction], Transaction, Dict[str, Any], Any],
) -> Union[List[Dict[str, Any]], Dict[str, Any], Any]:
    """Recursively converts a list of Transaction objects to a list of dictionaries."""
    if isinstance(obj, list):
        return [convert_to_dict(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_to_dict(value) for key, value in obj.items()}
    elif hasattr(obj, "__dict__"):
        return {
            key: convert_to_dict(value)
            for key, value in obj.__dict__.items()
            if not callable(value) and not key.startswith("__")
        }
    elif hasattr(obj, "__str__"):
        return str(obj)
    else:
        return obj


def get_recieve_txn_pytonapi(
    api_key: str, account_id: str, save_json: bool = False
) -> List[Dict[str, Any]]:
    """Retrieves transaction data using the pytonapi library and saves the data as a JSON file if requested."""
    tonapi = Tonapi(api_key=api_key)
    response = tonapi.blockchain.get_account_transactions(
        account_id=account_id, limit=1000
    )
    transactions_dict = convert_to_dict(response.transactions)
    assert isinstance(transactions_dict, list), "Expected a list of transactions"

    if save_json:
        d_today = datetime.date.today()
        num_transactions = len(transactions_dict)

        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)

        json_file_path = (
            output_dir / f"all_txns_pytonapi_N={num_transactions}_{d_today}.json"
        )

        if json_file_path.exists():
            overwrite = input(f"{json_file_path} already exists. Overwrite? (y/N) ")
            if overwrite.lower() != "y":
                print("File not saved.")
                return transactions_dict

        with open(json_file_path, "w") as f:
            json.dump(transactions_dict, f, indent=2)
        print(f"JSON file saved: {json_file_path}")

    return transactions_dict


def get_recieve_txn_tonapi(
    account_id: str, limit: int = 100, sort_order: str = "desc", save_json: bool = False
) -> List[Dict[str, Any]]:
    """Retrieves transaction data using the TON API and saves the data as a JSON file if requested."""
    url = f"https://tonapi.io/v2/blockchain/accounts/{account_id}/transactions"
    params: Dict[str, Union[int, str]] = {"limit": limit, "sort_order": sort_order}
    headers = {"accept": "application/json"}

    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    transactions_dict = data["transactions"]
    assert isinstance(transactions_dict, list), "Expected a list of transactions"

    if save_json:
        d_today = datetime.date.today()
        num_transactions = len(transactions_dict)

        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(exist_ok=True)

        json_file_path = (
            output_dir / f"all_txns_tonapi_N={num_transactions}_{d_today}.json"
        )

        if json_file_path.exists():
            overwrite = input(f"{json_file_path} already exists. Overwrite? (y/N) ")
            if overwrite.lower() != "y":
                print("File not saved.")
                return transactions_dict

        with open(json_file_path, "w") as f:
            json.dump(transactions_dict, f, indent=2)
        print(f"JSON file saved: {json_file_path}")

    return transactions_dict


class TonInfo(TypedDict):
    user_friendly_address: str
    raw_address: str
    pool_address: str
    get_member_use_address: str


class StakingInfo(TypedDict):
    calc_adjust_val: float
    calc_hour_val: int


class TonApiInfo(TypedDict):
    api_key: str


class FileSaveOption(TypedDict):
    save_allow_json: bool
    save_allow_csv: bool


class Config(TypedDict):
    ton_info: TonInfo
    staking_info: StakingInfo
    ton_api_info: TonApiInfo
    file_save_option: FileSaveOption


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, "config.toml")
    toml_config = TOMLFile(config_file_path)
    config_data = toml_config.read()
    if config_data is None:
        raise ValueError("Failed to read config file")
    config = cast(Config, config_data)

    API_KEY = config["ton_api_info"]["api_key"]
    ACCOUNT_ID = config["ton_info"]["user_friendly_address"]
    SAVE_JSON = config["file_save_option"]["save_allow_json"]
    SAVE_CSV = config["file_save_option"]["save_allow_csv"]

    # Retrieve transactions using pytonapi with API key
    if API_KEY:
        response_pytonapi = get_recieve_txn_pytonapi(
            API_KEY, ACCOUNT_ID, save_json=SAVE_JSON
        )

    # Retrieve transactions using TON API without API key
    response_nonapi = get_recieve_txn_tonapi(ACCOUNT_ID, save_json=SAVE_JSON)
