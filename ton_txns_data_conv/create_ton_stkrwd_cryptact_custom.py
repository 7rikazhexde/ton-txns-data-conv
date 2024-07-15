import datetime
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, cast

import pandas as pd
from get_ton_txns_api import (
    get_recieve_txn_pytonapi,
    get_transactions_v3,
    nano_to_amount,
)
from tomlkit.toml_file import TOMLFile


def create_cryptact_custom_data(
    transaction: Dict[str, Any], is_v3: bool = False
) -> Optional[List[Any]]:
    """Creates a list of data for a single transaction in Cryptact custom format.

    Args:
        transaction (Dict[str, Any]): A dictionary containing transaction data.
        is_v3 (bool, optional): Whether the transaction is from the v3 API. Defaults to False.

    Returns:
        Optional[List[Any]]: A list of transaction data in Cryptact custom format if the transaction
                             has a non-zero value, otherwise None.

    Note:
        - The function processes transaction data to create a row for the Cryptact custom CSV file.
        - Only transactions with a value greater than 0 in the `in_msg` field are processed.
        - The timestamp is converted to local time in the format "YYYY/MM/DD HH:MM:SS".
        - The transaction value is converted from nanotons to TON with 9 decimal places.
        - The "Action" field is set to "STAKING" for all transactions.
        - The "Source" field is set to "TON_WALLET" for all transactions.
        - The "Counter" currency is set to "JPY". This should be changed to the appropriate local currency if needed.
        - The transaction hash is included in the "Comment" field for reference.

    Example:
        >>> transaction = {
        ...     "hash": "abcdef1234567890",
        ...     "utime": 1625097600,
        ...     "in_msg": {"value": "1000000000"}
        ... }
        >>> create_cryptact_custom_data(transaction)
        ['2021/07/01 00:00:00', 'STAKING', 'TON_WALLET', 'TON', '1.000000000', '', 'JPY', 0, 'TON', 'TON_TXN_HASH: abcdef1234567890']
    """
    if is_v3:
        in_msg = transaction.get("in_msg", {})
        txn_val = in_msg.get("value")
        timestamp_field = "now"
    else:
        txn_val = transaction["in_msg"]["value"]
        timestamp_field = "utime"

    if txn_val and int(txn_val) != 0:
        txn_hash = transaction["hash"]
        local_time = datetime.datetime.fromtimestamp(
            int(transaction[timestamp_field])
        ).strftime("%Y/%m/%d %H:%M:%S")
        value_ton = f"{nano_to_amount(int(txn_val)):.9f}"

        return [
            f"'{local_time}",
            "STAKING",
            "TON_WALLET",
            "TON",
            value_ton,
            "",
            "JPY",  # Please change here to local currency.
            0,
            "TON",
            f"TON_TXN_HASH: {txn_hash}",
        ]
    return None


def create_cryptact_custom_csv(
    response: List[Dict[str, Any]],
    ascending: bool = True,
    filename: str = "",
    is_v3: bool = False,
) -> None:
    """Creates a custom CSV file for Cryptact based on the transaction data.

    Args:
        response (List[Dict[str, Any]]): The transaction data as a list of dictionaries.
        ascending (bool, optional): Whether to sort the data in ascending order. Defaults to True.
        filename (str, optional): The filename to use for the CSV file. Defaults to an empty string.
        is_v3 (bool, optional): Whether the transactions are from the v3 API. Defaults to False.

    Returns:
        None

    Note:
        - The CSV file is created in the custom file format for staking rewards in Cryptact.
          Refer to https://support.cryptact.com/hc/en-us/articles/360002571312-Custom-File-for-any-other-trades#menu210
          for more information on the custom file format.
        - Only transactions with a value greater than 0 in the `in_msg` field are included in the CSV file.
        - In the TON blockchain, there are no specific key/value pairs to distinguish between staking rewards and other transactions.
          Therefore, the CSV file may include transactions from other wallets that are not related to staking.
          Please manually remove any non-staking related data from the CSV file.
        - The CSV file is saved in the 'output' directory, which is created if it doesn't exist.
        - The filename includes the number of transactions and the current date.
        - If a file with the same name already exists, the user is prompted to confirm overwriting.
        - The CSV columns are: Timestamp, Action, Source, Base, Volume, Price, Counter, Fee, FeeCcy, Comment.

    Example:
        >>> transactions = [
        ...     {"hash": "abc123", "utime": 1625097600, "in_msg": {"value": "1000000000"}},
        ...     {"hash": "def456", "utime": 1625184000, "in_msg": {"value": "2000000000"}}
        ... ]
        >>> create_cryptact_custom_csv(transactions, filename="example")
        CSV file saved: /path/to/output/transactions_example_N=2_2023-07-15.csv
    """
    cryptact_custom_data = [
        data
        for transaction in response
        if (data := create_cryptact_custom_data(transaction, is_v3)) is not None
    ]

    df = pd.DataFrame(
        cryptact_custom_data,
        columns=[
            "Timestamp",
            "Action",
            "Source",
            "Base",
            "Volume",
            "Price",
            "Counter",
            "Fee",
            "FeeCcy",
            "Comment",
        ],
    )

    df = df.sort_values("Timestamp", ascending=ascending)
    d_today = datetime.date.today()
    num_transactions = len(df)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    if filename:
        csv_file_path = (
            output_dir / f"transactions_{filename}_N={num_transactions}_{d_today}.csv"
        )
    else:
        csv_file_path = output_dir / f"transactions_N={num_transactions}_{d_today}.csv"

    if csv_file_path.exists():
        overwrite = input(f"{csv_file_path} already exists. Overwrite? (y/N) ")
        if overwrite.lower() != "y":
            print("File not saved.")
            return

    df.to_csv(csv_file_path, index=False)
    print(f"CSV file saved: {csv_file_path}")


class TonInfo(TypedDict):
    user_friendly_address: str
    raw_address: str
    pool_address: str
    get_member_use_address: str
    transaction_history_period: float


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


def load_config() -> Config:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, "config.toml")
    toml_config = TOMLFile(config_file_path)
    config_data = toml_config.read()
    if config_data is None:
        raise ValueError("Failed to read config file")
    return cast(Config, config_data)


if __name__ == "__main__":
    config = load_config()
    API_KEY = config["ton_api_info"]["api_key"]
    ACCOUNT_ID = config["ton_info"]["user_friendly_address"]
    SAVE_JSON = config["file_save_option"]["save_allow_json"]
    SAVE_CSV = config["file_save_option"]["save_allow_csv"]
    TXNS_HISTORY_PERIOD = config["ton_info"]["transaction_history_period"]

    if API_KEY and SAVE_CSV:
        response_pytonapi = get_recieve_txn_pytonapi(
            API_KEY, ACCOUNT_ID, save_json=SAVE_JSON
        )
        create_cryptact_custom_csv(response_pytonapi, filename="pytonapi")
        print(f"PyTON API: Processed {len(response_pytonapi)} transactions")

    # if SAVE_CSV:
    #    response_nonapi = get_recieve_txn_tonapi(ACCOUNT_ID, save_json=SAVE_JSON)
    #    create_cryptact_custom_csv(response_nonapi, filename="tonapi")
    #    print(f"TON API: Processed {len(response_nonapi)} transactions")

    if SAVE_CSV:
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=TXNS_HISTORY_PERIOD)
        response_v3 = get_transactions_v3(
            account=ACCOUNT_ID,
            start_time=start_time,
            end_time=end_time,
            save_json=SAVE_JSON,
        )
        create_cryptact_custom_csv(response_v3, filename="tonindex_v3", is_v3=True)
        print(f"TON Index API v3: Processed {len(response_v3)} transactions")
