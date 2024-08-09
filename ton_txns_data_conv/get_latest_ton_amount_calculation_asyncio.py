import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple, cast

import aiohttp
from babel.numbers import get_currency_symbol
from pytoniq_core import Address
from pytoniq_core.boc.address import AddressError
from tomlkit.toml_file import TOMLFile

# Load configuration
script_dir = os.path.dirname(os.path.abspath(__file__))
config_file_path = os.path.join(script_dir, "config.toml")

if not os.path.exists(config_file_path):
    print(f"Error: Configuration file not found at {config_file_path}.")
    sys.exit(1)

try:
    toml_config = TOMLFile(config_file_path)
    config = toml_config.read()
except Exception as e:
    print(f"Error: Failed to read configuration file. {str(e)}")
    sys.exit(1)

# TON Address Info
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


async def fetch_data(session: aiohttp.ClientSession, url: str) -> Dict[str, Any]:
    async with session.get(url) as response:
        if response.status != 200:
            raise aiohttp.ClientResponseError(
                response.request_info,
                response.history,
                status=response.status,
                message=f"HTTP error {response.status}",
                headers=response.headers,
            )
        return cast(Dict[str, Any], await response.json())


async def get_latest_block(
    session: aiohttp.ClientSession,
) -> Tuple[int, datetime, datetime]:
    base_url = "https://mainnet-v4.tonhubapi.com/block/latest"
    data = await fetch_data(session, base_url)
    seqno = data["last"]["seqno"]
    ts_utc = datetime.fromtimestamp(data["now"], tz=timezone.utc)
    ts_jst = ts_utc.astimezone(timezone(timedelta(hours=9)))
    return seqno, ts_utc, ts_jst


async def get_staking_info(
    session: aiohttp.ClientSession,
    seqno: int,
    timestamp: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    base_url = f"https://mainnet-v4.tonhubapi.com/block/{seqno}/{pool_address}/run/get_member/{get_member_user_address}"
    data = await fetch_data(session, base_url)
    if "result" in data and len(data["result"]) >= 4:
        staked_amount = int(data["result"][0]["value"]) / 1e9
        pending_deposit = int(data["result"][1]["value"]) / 1e9
        pending_withdraw = int(data["result"][2]["value"]) / 1e9
        withdraw_available = int(data["result"][3]["value"]) / 1e9
        total_amount = sum(
            [staked_amount, pending_deposit, pending_withdraw, withdraw_available]
        )
        return {
            "Seqno": seqno,
            "Timestamp": timestamp.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S"),
            "Staked Amount": staked_amount,
            "Pending Deposit": pending_deposit,
            "Pending Withdraw": pending_withdraw,
            "Withdraw Available": withdraw_available,
            "Total Staked Amount": total_amount,
        }
    return None


async def ton_rate_by_ticker(
    session: aiohttp.ClientSession, ticker: str = "jpy"
) -> float:
    base_url = f"https://tonapi.io/v2/rates?tokens=ton&currencies=ton,{ticker}"
    data = await fetch_data(session, base_url)
    ticker = ticker.upper()
    return float(data["rates"]["TON"]["prices"][ticker])


async def get_ton_balance(
    session: aiohttp.ClientSession, user_friendly_address: str
) -> float:
    base_url = f"https://tonapi.io/v2/accounts/{user_friendly_address}"
    data = await fetch_data(session, base_url)
    return float(data["balance"]) / 1e9


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        try:
            latest_block = await get_latest_block(session)
            seqno, ts_utc, ts_jst = latest_block

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

            print(f"seqno: {seqno} / utc:{ts_utc} / jst:{ts_jst}")

            if staking_info:
                hold_ton = balance + staking_info["Total Staked Amount"]
                price = rate * hold_ton

                print(f"Timestamp: {staking_info['Timestamp']}")
                print(f"Total Staked Amount: {staking_info['Total Staked Amount']}")
                print(f"Balance: {balance}")
                print(f"Hold TON: {hold_ton}")
                print(f"Rate: {rate}")
                print(f"My account hold TON price: {symbol}{price}")
            else:
                print("Failed to get staking info.")

        except aiohttp.ClientError as e:
            print(f"Network error occurred: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
