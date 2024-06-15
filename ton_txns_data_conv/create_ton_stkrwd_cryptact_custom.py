import datetime
import os
from pathlib import Path
import pandas as pd
from typing import List, Dict, Any
from tomlkit.toml_file import TOMLFile
from get_ton_transactions import (
    get_recieve_txn_tonapi,
    get_recieve_txn_pytonapi,
    nano_to_amount,
)


def create_cryptact_custom_csv(
    response: List[Dict[str, Any]], ascending: bool = False, filename: str = ""
) -> None:
    """Creates a custom CSV file for Cryptact based on the transaction data.

    Args:
        response (List[Dict[str, Any]]): The transaction data as a list of dictionaries.
        ascending (bool, optional): Whether to sort the data in ascending order. Defaults to False.
        filename (str, optional): The filename to use for the CSV file. Defaults to an empty string.

    Note:
        - The CSV file is created in the custom file format for staking rewards in Cryptact.
          Refer to https://support.cryptact.com/hc/en-us/articles/360002571312-Custom-File-for-any-other-trades#menu210
          for more information on the custom file format.
        - Only transactions with a value greater than 0 in the `in_msg` field are included in the CSV file.
        - In the TON blockchain, there are no specific key/value pairs to distinguish between staking rewards and other transactions.
          Therefore, the CSV file may include transactions from other wallets that are not related to staking.
          Please manually remove any non-staking related data from the CSV file.

    Returns:
        None
    """
    cryptact_custom_data = []
    for transaction in response:
        # Extract transaction value and convert to TON
        txn_val = int(transaction["in_msg"]["value"])
        if txn_val != 0:
            txn_hash = transaction["hash"]
            local_time = datetime.datetime.fromtimestamp(
                int(transaction["utime"])
            ).strftime("%Y/%m/%d %H:%M:%S")
            value_ton = f"{nano_to_amount(int(txn_val)):.9f}"
            # Fees are not considered as they are paid by the sender
            # total_fee_ton = f"{nano_to_amount(transaction["total_fees"]):.9f}"

            cryptact_custom_data.append(
                [
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
            )

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

    # Sort the data in ascending order as the `sort_order` parameter is not supported in `get_account_transactions()`
    # detail:
    #  API: v2/blockchain/accounts/{account_id}
    #  Parameters: sort_order
    df = df.sort_index(ascending=ascending)
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


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_file_path = os.path.join(script_dir, "config.toml")
    toml_config = TOMLFile(config_file_path)
    config = toml_config.read()
    API_KEY = config.get("ton_api_info")["api_key"]
    ACCOUNT_ID = config.get("ton_info")["raw_address"]
    SAVE_JSON = config.get("file_save_option")["save_allow_json"]
    SAVE_CSV = config.get("file_save_option")["save_allow_csv"]

    # Retrieve transactions using pytonapi with API key
    if API_KEY:
        response_pytonapi = get_recieve_txn_pytonapi(
            API_KEY, ACCOUNT_ID, save_json=SAVE_JSON
        )
        if SAVE_CSV:
            create_cryptact_custom_csv(response_pytonapi, filename="pytonapi")

    # Retrieve transactions using TON API without API key
    response_nonapi = get_recieve_txn_tonapi(ACCOUNT_ID, save_json=SAVE_JSON)
    if SAVE_CSV:
        create_cryptact_custom_csv(response_nonapi, filename="tonapi")
