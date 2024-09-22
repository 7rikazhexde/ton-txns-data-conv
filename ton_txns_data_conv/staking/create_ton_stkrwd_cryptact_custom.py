import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast

import pandas as pd
import pytz

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


from ton_txns_data_conv.account.get_ton_txns_api import (
    get_transactions_v3,
    nano_to_amount,
)
from ton_txns_data_conv.utils.config_loader import load_config


def create_cryptact_custom_data(
    transaction: Dict[str, Any], transaction_timezone: str = "Asia/Tokyo"
) -> Optional[List[Union[str, int, float]]]:
    in_msg = transaction.get("in_msg", {})
    txn_val = in_msg.get("value")
    timestamp_field = "now"

    if txn_val and int(txn_val) != 0:
        txn_hash = transaction["hash"]

        # Use timezone-aware datetime
        utc_time = datetime.datetime.fromtimestamp(
            int(transaction[timestamp_field]), datetime.timezone.utc
        )
        tz = pytz.timezone(transaction_timezone)
        local_time = utc_time.astimezone(tz)
        time_str = local_time.strftime("%Y/%m/%d %H:%M:%S")
        value_ton = f"{nano_to_amount(int(txn_val)):.9f}"

        return cast(
            List[Union[str, int, float]],
            [
                f"'{time_str}",
                "STAKING",
                "TON_WALLET",
                "TON",
                value_ton,
                "",
                "JPY",
                0,
                "TON",
                f"TON_TXN_HASH: {txn_hash}",
            ],
        )
    return None


def create_cryptact_custom_csv(
    response: List[Dict[str, Any]],
    ascending: bool = True,
    filename: str = "tonindex_v3",
) -> None:
    cryptact_custom_data: List[List[Union[str, int, float]]] = [
        data
        for transaction in response
        if (data := create_cryptact_custom_data(transaction)) is not None
    ]

    if not cryptact_custom_data:
        print("No valid transactions found. CSV file not created.")
        return

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

    output_dir = project_root / "ton_txns_data_conv" / "output"
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


def main() -> None:
    config = load_config()
    ACCOUNT_ID: str = config["ton_info"]["user_friendly_address"]
    SAVE_JSON: bool = config["file_save_option"]["save_allow_json"]
    SAVE_CSV: bool = config["file_save_option"]["save_allow_csv"]
    TXNS_HISTORY_PERIOD: int = config["ton_info"]["transaction_history_period"]

    if SAVE_CSV:
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(days=TXNS_HISTORY_PERIOD)
        response_v3 = get_transactions_v3(
            account=ACCOUNT_ID,
            start_time=start_time,
            end_time=end_time,
            save_json=SAVE_JSON,
        )
        create_cryptact_custom_csv(response_v3)
        print(f"TON Index API v3: Processed {len(response_v3)} transactions")


if __name__ == "__main__":  # pragma: no cover
    main()
