import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import requests
from babel import Locale
from babel.numbers import get_currency_symbol
from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ton_txns_data_conv.utils.config_loader import load_config

config = load_config()

DEFAULT_UF_ADDRESS: str = ""
BASIC_WORKCHAIN_ADDRESS: str = ""


def initialize_address() -> None:
    global BASIC_WORKCHAIN_ADDRESS
    global DEFAULT_UF_ADDRESS
    DEFAULT_UF_ADDRESS = config.get("ton_info", {}).get("user_friendly_address", "")
    try:
        address = Address(DEFAULT_UF_ADDRESS)
        BASIC_WORKCHAIN_ADDRESS = address.to_str(
            is_user_friendly=True,
            is_bounceable=True,
            is_url_safe=True,
            is_test_only=False,
        )
    except (IndexError, AddressError) as e:
        print(
            f"Warning: Invalid address format ({type(e).__name__}). Using empty address."
        )
        sys.exit(1)


DEFAULT_POOL_ADDRESS = config.get("ton_info", {}).get("pool_address", "")
DEFAULT_GET_MEMBER_USER_ADDRESS = config.get("ton_info", {}).get(
    "get_member_use_address", ""
)
DEFAULT_LOCAL_TIMEZONE = config.get("staking_info", {}).get("local_timezone", 0.1)
DEFAULT_COUNTER_VAL = config.get("cryptact_info", {}).get("counter", "JPY")
TZ = timezone(timedelta(hours=DEFAULT_LOCAL_TIMEZONE))

try:
    symbol = get_currency_symbol(DEFAULT_COUNTER_VAL, locale=Locale("ja_JP"))
except (ValueError, TypeError):
    symbol = "¥"


ENABLE_TRACING = config.get("debug_info", {}).get("enable_tracing", False)


def create_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def log_request(method: str, url: str) -> None:
    if ENABLE_TRACING:
        print(f"Sending request: {method} {url}")


def log_response(response: requests.Response) -> None:
    if ENABLE_TRACING:
        print(f"Received response: {response.status_code} from {response.url}")


def make_request(
    session: requests.Session, method: str, url: str, **kwargs: Any
) -> requests.Response:
    log_request(method, url)
    start_time = time.time()
    response = session.request(method, url, **kwargs)
    end_time = time.time()
    log_response(response)
    if ENABLE_TRACING:
        print(f"Request took {end_time - start_time:.2f} seconds")
    response.raise_for_status()
    return response


def get_latest_block(session: requests.Session) -> Tuple[int, datetime, datetime]:
    base_url = "https://mainnet-v4.tonhubapi.com/block/latest"
    response = make_request(session, "GET", base_url)
    data = response.json()
    seqno = data["last"]["seqno"]
    ts_utc = datetime.fromtimestamp(data["now"], tz=timezone.utc)
    ts_local = ts_utc.astimezone(TZ)
    return seqno, ts_utc, ts_local


def get_staking_info(
    session: requests.Session,
    seqno: int,
    timestamp: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    base_url = f"https://mainnet-v4.tonhubapi.com/block/{seqno}/{pool_address}/run/get_member/{get_member_user_address}"
    response = make_request(session, "GET", base_url)
    data = response.json()
    if "result" in data and len(data["result"]) >= 4:
        values = [int(data["result"][i]["value"]) / 1e9 for i in range(4)]
        total_amount = sum(values)
        return {
            "Seqno": seqno,
            "Timestamp": timestamp.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "Staked Amount": values[0],
            "Pending Deposit": values[1],
            "Pending Withdraw": values[2],
            "Withdraw Available": values[3],
            "Total Staked Amount": total_amount,
        }
    return None


def ton_rate_by_ticker(session: requests.Session, ticker: str = "jpy") -> float:
    base_url = f"https://tonapi.io/v2/rates?tokens=ton&currencies=ton,{ticker}"
    response = make_request(session, "GET", base_url)
    data = response.json()
    ticker = ticker.upper()
    return float(data["rates"]["TON"]["prices"][ticker])


def get_ton_balance(session: requests.Session, user_friendly_address: str) -> float:
    base_url = f"https://tonapi.io/v2/accounts/{user_friendly_address}"
    response = make_request(session, "GET", base_url)
    data = response.json()
    return float(data["balance"]) / 1e9


def main() -> None:
    initialize_address()
    session = create_session()
    try:
        seqno, ts_utc, ts_local = get_latest_block(session)
        print(f"seqno: {seqno} / utc:{ts_utc} / local:{ts_local}")

        balance = get_ton_balance(session, DEFAULT_UF_ADDRESS)
        response = get_staking_info(
            session,
            seqno,
            ts_utc,
            DEFAULT_POOL_ADDRESS,
            DEFAULT_GET_MEMBER_USER_ADDRESS,
        )

        if response:
            print(f"Timestamp: {response['Timestamp']}")
            print(f"Total Staked Amount: {response['Total Staked Amount']:.9f}")
            print(f"Balance: {balance:.9f}")
            hold_ton = balance + response["Total Staked Amount"]
            print(f"Hold TON: {hold_ton:.9f}")
            rate = ton_rate_by_ticker(session)
            price = rate * hold_ton
            print(f"Rate: {rate:.2f}")
            print(f"My account hold TON price: {symbol}{price:.2f}")
        else:
            print("Failed to get staking info.")
    except requests.RequestException as e:
        print(f"An error occurred: {e}")
    finally:
        session.close()


if __name__ == "__main__":  # pragma: no cover
    main()
