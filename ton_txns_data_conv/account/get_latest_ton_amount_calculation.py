import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from datetime import datetime, timedelta, timezone
from typing import Any, Coroutine, Dict, List, Optional, Tuple, cast

import httpx
from babel import Locale
from babel.numbers import get_currency_symbol
from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError

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
DEFAULT_LOCAL_TIMEZONE = config.get("staking_info", {}).get("local_timezone", 9)
DEFAULT_COUNTER_VAL = config.get("cryptact_info", {}).get("counter", "JPY")
TZ = timezone(timedelta(hours=DEFAULT_LOCAL_TIMEZONE))

try:
    symbol = get_currency_symbol(DEFAULT_COUNTER_VAL, locale=Locale("ja_JP"))
except (ValueError, TypeError):
    symbol = "¥"

BASE_URL_TONHUB = "https://mainnet-v4.tonhubapi.com"
BASE_URL_TONAPI = "https://tonapi.io/v2"

ENABLE_TRACING = config.get("debug_info", {}).get("enable_tracing", False)


async def log_request(request: httpx.Request) -> None:
    print(f"Sending request: {request.method} {request.url}", flush=True)


async def log_response(response: httpx.Response) -> None:
    print(
        f"Received response: {response.status_code} from {response.request.url}",
        flush=True,
    )


class TracingClient(httpx.AsyncClient):
    async def send(
        self,
        request: httpx.Request,
        *,
        stream: bool = False,
        auth: Optional[httpx.Auth] = None,
        follow_redirects: bool = True,
    ) -> httpx.Response:
        if ENABLE_TRACING:
            await log_request(request)
        response = await super().send(
            request, stream=stream, auth=auth, follow_redirects=follow_redirects
        )
        if ENABLE_TRACING:
            await log_response(response)
        return response


async def fetch_data(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    response: httpx.Response = await client.get(url)
    response.raise_for_status()
    return cast(Dict[str, Any], response.json())


async def get_latest_block(
    client: httpx.AsyncClient,
) -> Tuple[int, datetime, datetime]:
    data = await fetch_data(client, f"{BASE_URL_TONHUB}/block/latest")
    seqno = data["last"]["seqno"]
    ts_utc = datetime.fromtimestamp(data["now"], tz=timezone.utc)
    ts_local = ts_utc.astimezone(TZ)
    return seqno, ts_utc, ts_local


async def get_staking_info(
    client: httpx.AsyncClient,
    seqno: int,
    timestamp: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    data = await fetch_data(
        client,
        f"{BASE_URL_TONHUB}/block/{seqno}/{pool_address}/run/get_member/{get_member_user_address}",
    )
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


async def ton_rate_by_ticker(client: httpx.AsyncClient, ticker: str = "jpy") -> float:
    data = await fetch_data(
        client, f"{BASE_URL_TONAPI}/rates?tokens=ton&currencies=ton,{ticker}"
    )
    return float(data["rates"]["TON"]["prices"][ticker.upper()])


async def get_ton_balance(
    client: httpx.AsyncClient, user_friendly_address: str
) -> float:
    data = await fetch_data(
        client, f"{BASE_URL_TONAPI}/accounts/{user_friendly_address}"
    )
    return float(data["balance"]) / 1e9


async def main() -> None:
    initialize_address()
    timeout: httpx.Timeout = httpx.Timeout(10.0)
    limits: httpx.Limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async with TracingClient(timeout=timeout, limits=limits) as client:
        try:
            latest_block: Tuple[int, datetime, datetime] = await get_latest_block(
                client
            )
            seqno, ts_utc, ts_local = latest_block

            tasks: List[Coroutine] = [
                get_staking_info(
                    client,
                    seqno,
                    ts_utc,
                    DEFAULT_POOL_ADDRESS,
                    DEFAULT_GET_MEMBER_USER_ADDRESS,
                ),
                get_ton_balance(client, DEFAULT_UF_ADDRESS),
                ton_rate_by_ticker(client, DEFAULT_COUNTER_VAL.lower()),
            ]

            results: Tuple[
                Optional[Dict[str, Any]], float, float
            ] = await asyncio.gather(*tasks)
            staking_info, balance, rate = results

            print(f"seqno: {seqno} / utc:{ts_utc} / local:{ts_local}")

            if staking_info:
                hold_ton: float = balance + staking_info["Total Staked Amount"]
                price: float = rate * hold_ton

                print(f"Timestamp: {staking_info['Timestamp']}")
                print(f"Total Staked Amount: {staking_info['Total Staked Amount']:.9f}")
                print(f"Balance: {balance:.9f}")
                print(f"Hold TON: {hold_ton:.9f}")
                print(f"Rate: {rate:.2f}")
                print(f"My account hold TON price: {symbol}{price:.2f}")
            else:
                print("Failed to get staking info.")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"Network error occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
