import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, cast

import aiohttp
from aiohttp import (
    ClientTimeout,
    TCPConnector,
    TraceConfig,
    TraceRequestEndParams,
    TraceRequestStartParams,
)
from babel.numbers import get_currency_symbol
from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError

from ton_txns_data_conv.utils.config_loader import load_config

config = load_config()

DEFAULT_UF_ADDRESS = config.get("ton_info", {}).get("user_friendly_address", "")

if not DEFAULT_UF_ADDRESS:
    print("Error: Please set 'user_friendly_address' in the config.toml file.")
    sys.exit(1)

try:
    address = Address(DEFAULT_UF_ADDRESS)
    BASIC_WORKCHAIN_ADDRESS = address.to_str(
        is_user_friendly=True, is_bounceable=True, is_url_safe=True, is_test_only=False
    )
except AddressError as e:
    print(f"Error: Invalid user_friendly_address. {str(e)}")
    sys.exit(1)
except Exception as e:
    print(f"Error: An unexpected error occurred while creating the address. {str(e)}")
    sys.exit(1)

BASIC_WORKCHAIN_ADDRESS = address.to_str(
    is_user_friendly=True, is_bounceable=True, is_url_safe=True, is_test_only=False
)
# Ref: https://docs.ton.org/develop/dapps/cookbook#what-flags-are-there-in-user-friendly-addresses

DEFAULT_POOL_ADDRESS = config.get("ton_info", {}).get("pool_address", "")
DEFAULT_GET_MEMBER_USER_ADDRESS = config.get("ton_info", {}).get(
    "get_member_use_address", ""
)
DEFAULT_LOCAL_TIMEZONE = config.get("staking_info", {}).get("local_timezone", 0.1)
DEFAULT_COUNTER_VAL = config.get("cryptact_info", {}).get("counter", "")
TZ = timezone(timedelta(hours=DEFAULT_LOCAL_TIMEZONE))

symbol = get_currency_symbol(DEFAULT_COUNTER_VAL)

ENABLE_TRACING = config.get("debug_info", {}).get("enable_tracing", False)


def create_trace_config(enable_tracing: bool) -> Optional[TraceConfig]:
    if enable_tracing:
        trace_config = TraceConfig()
        trace_config.on_request_start.append(on_request_start)
        trace_config.on_request_end.append(on_request_end)
        return trace_config
    return None


BASE_URL_TONHUB = "https://mainnet-v4.tonhubapi.com"
BASE_URL_TONAPI = "https://tonapi.io/v2"


async def fetch_data(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    async with session.get(url) as response:
        response.raise_for_status()
        return cast(Dict[str, Any], await response.json())


async def get_latest_block(
    session: aiohttp.ClientSession,
) -> Tuple[int, datetime, datetime]:
    data = await fetch_data(session, f"{BASE_URL_TONHUB}/block/latest")
    seqno = data["last"]["seqno"]
    ts_utc = datetime.fromtimestamp(data["now"], tz=timezone.utc)
    ts_local = ts_utc.astimezone(TZ)
    return seqno, ts_utc, ts_local


async def get_staking_info(
    session: aiohttp.ClientSession,
    seqno: int,
    timestamp: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    data = await fetch_data(
        session,
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


async def ton_rate_by_ticker(
    session: aiohttp.ClientSession, ticker: str = "jpy"
) -> float:
    data = await fetch_data(
        session, f"{BASE_URL_TONAPI}/rates?tokens=ton&currencies=ton,{ticker}"
    )
    return float(data["rates"]["TON"]["prices"][ticker.upper()])


async def get_ton_balance(
    session: aiohttp.ClientSession, user_friendly_address: str
) -> float:
    data = await fetch_data(
        session, f"{BASE_URL_TONAPI}/accounts/{user_friendly_address}"
    )
    return float(data["balance"]) / 1e9


async def on_request_start(
    session: Any, trace_config_ctx: Any, params: TraceRequestStartParams
) -> None:
    print(f"Sending request: {params.url}")


async def on_request_end(
    session: Any, trace_config_ctx: Any, params: TraceRequestEndParams
) -> None:
    print(f"Received response: {params.response.status}")


async def main() -> None:
    trace_config = create_trace_config(ENABLE_TRACING)

    connector = TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True)
    timeout = ClientTimeout(total=10, connect=5)

    client_kwargs = {
        "connector": connector,
        "timeout": timeout,
    }
    if trace_config:
        client_kwargs["trace_configs"] = [trace_config]

    async with aiohttp.ClientSession(**client_kwargs) as session:
        try:
            latest_block = await get_latest_block(session)
            seqno, ts_utc, ts_local = latest_block

            tasks = [
                get_staking_info(
                    session,
                    seqno,
                    ts_utc,
                    DEFAULT_POOL_ADDRESS,
                    DEFAULT_GET_MEMBER_USER_ADDRESS,
                ),
                get_ton_balance(session, DEFAULT_UF_ADDRESS),
                ton_rate_by_ticker(session, DEFAULT_COUNTER_VAL.lower()),
            ]

            results = await asyncio.gather(*tasks)
            staking_info, balance, rate = cast(
                Tuple[Optional[Dict[str, Any]], float, float], results
            )

            print(f"seqno: {seqno} / utc:{ts_utc} / local:{ts_local}")

            if staking_info:
                hold_ton = balance + staking_info["Total Staked Amount"]
                price = rate * hold_ton

                print(f"Timestamp: {staking_info['Timestamp']}")
                print(f"Total Staked Amount: {staking_info['Total Staked Amount']:.9f}")
                print(f"Balance: {balance:.9f}")
                print(f"Hold TON: {hold_ton:.9f}")
                print(f"Rate: {rate:.2f}")
                print(f"My account hold TON price: {symbol}{price:.2f}")
            else:
                print("Failed to get staking info.")

        except aiohttp.ClientResponseError as e:
            print(f"HTTP error occurred: {e.status} - {e.message}")
        except aiohttp.ClientError as e:
            print(f"Network error occurred: {e}")
        except asyncio.TimeoutError:
            print("Request timed out")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
