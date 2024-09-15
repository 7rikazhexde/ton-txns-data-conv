import asyncio
import gzip
import json
import sys
from pathlib import Path

from aiohttp import ClientResponseError, ClientSession

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
DEFAULT_LOCAL_TIMEZONE = config.get("staking_info", {}).get("local_timezone", 0.1)
DEFAULT_COUNTER_VAL = config.get("cryptact_info", {}).get("counter", "JPY")
TZ = timezone(timedelta(hours=DEFAULT_LOCAL_TIMEZONE))

try:
    symbol = get_currency_symbol(DEFAULT_COUNTER_VAL, locale=Locale("ja_JP"))
except (ValueError, TypeError):
    symbol = "¥"

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


async def fetch_data(session: ClientSession, url: str) -> Dict[str, Any]:
    # print(f"Fetching data from: {url}")
    async with session.get(url) as response:
        # print(f"Response status: {response.status}")
        # print(f"Response headers: {response.headers}")

        if response.status >= 400:
            raise ClientResponseError(
                request_info=response.request_info,
                history=response.history,
                status=response.status,
                message=f"HTTP Error {response.status}: {response.reason}",
            )

        content = await response.read()
        # print(f"Raw content length: {len(content)} bytes")

        if response.headers.get("Content-Encoding") == "gzip":
            # print("Content-Encoding is gzip, attempting to decompress")
            try:
                decompressed_content = gzip.decompress(content)
                # print("Successfully decompressed gzip content")
                data_str = decompressed_content.decode("utf-8")
            except gzip.BadGzipFile:
                # print("Failed to decompress as gzip, treating as uncompressed")
                data_str = content.decode("utf-8")
        else:
            # print("Content is not gzip encoded")
            data_str = content.decode("utf-8")

        # print(f"Data string preview: {data_str[:200]}...")  # 最初の200文字を表示

        data = json.loads(data_str)

        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object, got {type(data).__name__}")

        # print(f"Parsed data: {data}")
        return data


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
    initialize_address()
    trace_config = create_trace_config(ENABLE_TRACING)

    connector = TCPConnector(limit=10, force_close=True, enable_cleanup_closed=True)
    timeout = ClientTimeout(total=10, connect=5)

    client_kwargs = {
        "connector": connector,
        "timeout": timeout,
        "auto_decompress": True,
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


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
