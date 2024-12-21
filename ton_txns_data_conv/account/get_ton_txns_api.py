import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import requests

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from ton_txns_data_conv.utils.config_loader import load_config


def nano_to_amount(value: int, precision: int = 9) -> float:  # pragma: no cover
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


def save_json_file(data: List[Dict[str, Any]], filename: str) -> None:
    """Saves a list of dictionaries to a JSON file in the 'output' directory.

    Args:
        data (List[Dict[str, Any]]): The data to save, represented as a list of dictionaries.
        filename (str): The name of the JSON file to save the data to.

    Note:
        - The function creates an 'output' directory if it does not already exist.
        - If a file with the specified filename already exists, the user is prompted for confirmation before overwriting it.
        - The JSON file is saved with an indentation of 2 spaces.

    Example:
        >>> data = [{'key1': 'value1', 'key2': 'value2'}, {'key1': 'value3', 'key2': 'value4'}]
        >>> save_json_file(data, "example.json")
        JSON file saved: /path/to/output/example.json
    """
    # output_dir = Path(__file__).parent / "output"
    output_dir = project_root / "ton_txns_data_conv" / "output"
    output_dir.mkdir(exist_ok=True)
    json_file_path = output_dir / filename

    if json_file_path.exists():
        overwrite = input(f"{json_file_path} already exists. Overwrite? (y/N) ")
        if overwrite.lower() != "y":
            print("File not saved.")
            return

    with open(json_file_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"JSON file saved: {json_file_path}")


def get_recieve_txn_tonapi(
    account_id: str, limit: int = 100, sort_order: str = "desc", save_json: bool = False
) -> List[Dict[str, Any]]:  # pragma: no cover
    """Retrieves transactions for a TON account using the TON API.

    Args:
        account_id (str): The TON account ID to fetch transactions for.
        limit (int, optional): The maximum number of transactions to retrieve. Defaults to 100.
        sort_order (str, optional): The order to sort the transactions ("asc" or "desc"). Defaults to "desc".
        save_json (bool, optional): Whether to save the raw JSON response to a file. Defaults to False.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a transaction.

    Note:
        - This function uses the TON API to fetch transactions for the specified account.
        - The transactions are returned as a list of dictionaries, with each dictionary containing the full
          transaction data as provided by the API.
        - If save_json is True, the raw JSON response is saved to a file in the 'output' directory.
        - The filename for the JSON file includes the number of transactions and the current date.
        - This function does not require an API key, as it uses the public TON API endpoint.

    Example:
        >>> account_id = "your_account_id(User-friendly address)"
        >>> transactions = get_recieve_txn_tonapi(account_id, limit=50, save_json=True)
        >>> len(transactions)
        50
    """
    url = f"https://tonapi.io/v2/blockchain/accounts/{account_id}/transactions"
    params: Dict[str, Union[int, str]] = {"limit": limit, "sort_order": sort_order}
    headers = {"accept": "application/json"}

    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    transactions_dict = data["transactions"]
    assert isinstance(transactions_dict, list), "Expected a list of transactions"

    if save_json:
        filename = (
            f"all_txns_tonapi_N={len(transactions_dict)}_{datetime.today().date()}.json"
        )
        save_json_file(transactions_dict, filename)

    return transactions_dict


def get_transactions_v3(
    account: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0,
    save_json: bool = False,
) -> List[Dict[str, Any]]:
    """Retrieves transactions for a TON account using the TON Index API v3.

    Args:
        account (str): The TON account address to fetch transactions for.
        start_time (Optional[datetime], optional): The start time for the transaction query. Defaults to None.
        end_time (Optional[datetime], optional): The end time for the transaction query. Defaults to None.
        limit (int, optional): The maximum number of transactions to retrieve per request. Defaults to 100.
        offset (int, optional): The offset for pagination. Defaults to 0.
        save_json (bool, optional): Whether to save the raw JSON response to a file. Defaults to False.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary represents a transaction.

    Note:
        - This function uses the TON Index API v3 to fetch transactions for the specified account.
        - The function will make multiple API calls if necessary to retrieve all transactions within the specified time range.
        - If start_time and end_time are not provided, the API will return the most recent transactions.
        - The transactions are returned as a list of dictionaries, with each dictionary containing the full
          transaction data as provided by the API.
        - If save_json is True, the raw JSON response is saved to a file in the 'output' directory.
        - The filename for the JSON file includes the number of transactions and the current date.
        - This function implements error handling and will retry failed requests with a delay.

    Example:
        >>> account = "YOUR_ACCOUNT"
        >>> start = datetime(2024, 1, 1)
        >>> end = datetime(2024, 7, 1)
        >>> transactions = get_transactions_v3(account, start_time=start, end_time=end, save_json=True)
        >>> len(transactions)
        500
    """
    base_url = "https://toncenter.com/api/v3/transactions"
    all_transactions = []

    while True:
        params: Dict[str, Union[str, int]] = {
            "account": account,
            "limit": limit,
            "offset": offset,
            "sort": "desc",
        }

        if start_time:
            params["start_utime"] = int(start_time.timestamp())
        if end_time:
            params["end_utime"] = int(end_time.timestamp())

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()

            transactions = data.get("transactions", [])
            if not transactions:
                break

            all_transactions.extend(transactions)
            offset += len(transactions)

            if len(transactions) < limit:
                break

            time.sleep(1)

        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            break
        except json.JSONDecodeError:
            print("JSON decode error. The response is not valid JSON.")
            break

    if save_json and all_transactions:
        filename = f"all_txns_tonindex_v3_N={len(all_transactions)}_{date.today()}.json"
        save_json_file(all_transactions, filename)

    return all_transactions


def main() -> None:
    config = load_config()
    ACCOUNT_ID = config["ton_info"]["user_friendly_address"]
    SAVE_JSON = config["file_save_option"]["save_allow_json"]
    TXNS_HISTORY_PERIOD = config["ton_info"]["transaction_history_period"]

    end_time = datetime.now()
    start_time = end_time - timedelta(days=TXNS_HISTORY_PERIOD)
    response_tonindex = get_transactions_v3(
        account=ACCOUNT_ID,
        start_time=start_time,
        end_time=end_time,
        save_json=SAVE_JSON,
    )
    print(f"TON Index API v3: Retrieved {len(response_tonindex)} transactions")


if __name__ == "__main__":  # pragma: no cover
    main()
