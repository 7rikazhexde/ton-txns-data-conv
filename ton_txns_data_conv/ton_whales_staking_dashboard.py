"""
TON Whales Staking Amount History

This script creates a Dash web application to visualize and analyze staking history
for TON (The Open Network) using the TON Whales staking pool.

The application fetches staking data from the TON blockchain, displays it in a graph,
and allows users to save staking reward history.
"""

import asyncio
import csv
import os
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import dash
import pandas as pd
import plotly.graph_objs as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output, State
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

# Initialize default values
DEFAULT_TIMEZONE_OFFSET = config.get("staking_info", {}).get("timezone_offset", 0.1)
DEFAULT_DAILY_FETCH_HOUR = config.get("staking_info", {}).get("daily_fech_hour", 0.1)
DEFAULT_COUNTER_VAL = config.get("cryptact_info", {}).get("counter", "")
TZ = timezone(timedelta(hours=DEFAULT_DAILY_FETCH_HOUR))

# Save Option
SAVE_ALLOW_STKRWD = config.get("file_save_option", {}).get("save_allow_stkrwd", False)


async def get_latest_block(session: aiohttp.ClientSession) -> Tuple[int, datetime]:
    """
    Fetch the latest block information from the TON blockchain.

    Args:
        session (aiohttp.ClientSession): An active aiohttp client session.

    Returns:
        Tuple[int, datetime]: The sequence number of the latest block and its timestamp.
    """
    async with session.get("https://mainnet-v4.tonhubapi.com/block/latest") as response:
        data = await response.json()
        return data["last"]["seqno"], datetime.fromtimestamp(
            data["now"], tz=timezone.utc
        )


async def get_block_by_unix_time(
    session: aiohttp.ClientSession, unix_time: int
) -> Tuple[Optional[int], Optional[datetime]]:
    """
    Fetch block information for a specific Unix timestamp.

    Args:
        session (aiohttp.ClientSession): An active aiohttp client session.
        unix_time (int): The Unix timestamp to query.

    Returns:
        Tuple[Optional[int], Optional[datetime]]: The sequence number and timestamp of the block,
        or (None, None) if the block doesn't exist.
    """
    async with session.get(
        f"https://mainnet-v4.tonhubapi.com/block/utime/{int(unix_time)}"
    ) as response:
        data = await response.json()
        if data["exist"]:
            shard_data = data["block"]["shards"][0]
            seqno = shard_data["seqno"]
            timestamp = shard_data.get("timestamp", int(unix_time))
            return seqno, datetime.fromtimestamp(timestamp, tz=timezone.utc)
        else:
            return None, None


async def get_staking_info(
    session: aiohttp.ClientSession,
    seqno: int,
    timestamp: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch staking information for a specific block and pool address.

    Args:
        session (aiohttp.ClientSession): An active aiohttp client session.
        seqno (int): The sequence number of the block to query.
        timestamp (datetime): The timestamp of the block.
        pool_address (str): The address of the staking pool.
        get_member_user_address (str): The address of the user to query.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing staking information,
        or None if the information couldn't be retrieved.
    """
    url = f"https://mainnet-v4.tonhubapi.com/block/{seqno}/{pool_address}/run/get_member/{get_member_user_address}"
    async with session.get(url) as response:
        data = await response.json()
        if "result" in data and len(data["result"]) >= 4:
            return {
                "Timestamp": timestamp.astimezone(TZ),
                "Seqno": seqno,
                "Staked Amount": int(data["result"][0]["value"]) / 1e9,
                "Pending Deposit": int(data["result"][1]["value"]) / 1e9,
                "Pending Withdraw": int(data["result"][2]["value"]) / 1e9,
                "Withdraw Available": int(data["result"][3]["value"]) / 1e9,
            }
        else:
            return None


async def get_staking_history(
    start_date: datetime,
    end_date: datetime,
    hour: int,
    pool_address: str,
    get_member_user_address: str,
) -> List[Dict[str, Any]]:
    """
    Fetch staking history for a given date range.

    Args:
        start_date (datetime): The start date of the range to query.
        end_date (datetime): The end date of the range to query.
        hour (int): The hour of the day to query for each date.
        pool_address (str): The address of the staking pool.
        get_member_user_address (str): The address of the user to query.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing staking information for each day in the range.
    """
    async with aiohttp.ClientSession() as session:
        tasks = []
        current_date = start_date.replace(hour=hour, minute=0, second=0, microsecond=0)
        while current_date <= end_date:
            tasks.append(
                get_block_and_staking_info(
                    session, current_date, pool_address, get_member_user_address
                )
            )
            current_date += timedelta(days=1)

        results = await asyncio.gather(*tasks)
        return [result for result in results if result is not None]


async def get_block_and_staking_info(
    session: aiohttp.ClientSession,
    target_time: datetime,
    pool_address: str,
    get_member_user_address: str,
) -> Optional[Dict[str, Any]]:
    """
    Fetch block and staking information for a specific time.

    Args:
        session (aiohttp.ClientSession): An active aiohttp client session.
        target_time (datetime): The time to query.
        pool_address (str): The address of the staking pool.
        get_member_user_address (str): The address of the user to query.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing staking information,
        or None if the information couldn't be retrieved.
    """
    seqno, actual_time = await get_block_by_unix_time(
        session, int(target_time.timestamp())
    )
    if seqno and actual_time:
        return await get_staking_info(
            session, seqno, actual_time, pool_address, get_member_user_address
        )
    return None


def calculate_staking_rewards(df: pd.DataFrame, adjust_val: float) -> pd.DataFrame:
    """
    Calculate staking rewards based on the difference in staked amounts.

    Args:
        df (pd.DataFrame): A DataFrame containing staking history.
        adjust_val (float): The threshold value for considering a difference as a reward.

    Returns:
        pd.DataFrame: A DataFrame containing calculated staking rewards.
    """
    results = []
    for i in range(1, len(df)):
        current_amount = df.iloc[i]["Staked Amount"]
        previous_amount = df.iloc[i - 1]["Staked Amount"]
        difference = current_amount - previous_amount

        if 0 < difference <= adjust_val:
            timestamp = pd.to_datetime(df.iloc[i]["Timestamp"])
            results.append(
                {
                    "Timestamp": f"'{timestamp.strftime('%Y/%m/%d %H:%M:%S')}",
                    "Action": "STAKING",
                    "Source": "TON_WALLET",
                    "Base": "TON",
                    "Volume": difference,
                    "Price": "",
                    "Counter": DEFAULT_COUNTER_VAL,
                    "Fee": 0,
                    "FeeCcy": "TON",
                    "Comment": f"Seqno Segment:{df.iloc[i-1]['Seqno']} - {df.iloc[i]['Seqno']}",
                }
            )

    return pd.DataFrame(results)


# Initialize Dash app
app = Dash(__name__, assets_folder="assets")
app.title = "TON Whales Staking Amount History"

app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks === undefined || n_clicks === 0) {
            return {display: 'none'};
        }
        var content = document.getElementById('tooltip-content');
        return {display: content.style.display === 'block' ? 'none' : 'block'};
    }
    """,
    Output("tooltip-content", "style"),
    Input("tooltip-trigger", "n_clicks"),
)


def toggle_tooltip_1(n_clicks: int) -> Dict[str, str]:
    """
    Toggle the visibility of the first tooltip.

    This clientside callback function controls the display of the tooltip content
    for the 'Timezone Offset' input. It is triggered by clicks on the tooltip trigger element.

    Args:
        n_clicks (int): The number of times the tooltip trigger has been clicked.
                        Note: In practice, this argument is handled by the JavaScript code.

    Returns:
        Dict[str, str]: A dictionary with a 'display' key, which is either 'block' or 'none'.
                        Note: The actual return value is generated by the JavaScript code.

    Note:
        This function is a placeholder for the clientside callback.
        The actual toggling logic is handled by the JavaScript code above.
    """
    return {"display": "none"}


app.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks === undefined || n_clicks === 0) {
            return {display: 'none'};
        }
        var content = document.getElementById('tooltip-content-2');
        return {display: content.style.display === 'block' ? 'none' : 'block'};
    }
    """,
    Output("tooltip-content-2", "style"),
    Input("tooltip-trigger-2", "n_clicks"),
)


def toggle_tooltip_2(n_clicks: int) -> Dict[str, str]:
    """
    Toggle the visibility of the second tooltip.

    This clientside callback function controls the display of the tooltip content
    for the 'Staking Pool Member Address' input. It is triggered by clicks on the
    tooltip trigger element.

    Args:
        n_clicks (int): The number of times the tooltip trigger has been clicked.
                        Note: In practice, this argument is handled by the JavaScript code.

    Returns:
        Dict[str, str]: A dictionary with a 'display' key, which is either 'block' or 'none'.
                        Note: The actual return value is generated by the JavaScript code.

    Note:
        This function is a placeholder for the clientside callback.
        The actual toggling logic is handled by the JavaScript code above.
    """
    return {"display": "none"}


def create_layout() -> html.Div:
    """
    Create the layout for the Dash application.

    Returns:
        html.Div: The main container for the application layout.
    """
    return html.Div(
        className="container",
        children=[
            html.H1("TON Whales Staking Amount History", className="header"),
            html.Div(
                className="input-group",
                children=[
                    html.Label("Pool Address:", className="label"),
                    dcc.Input(
                        id="pool-address-input",
                        type="text",
                        value=DEFAULT_POOL_ADDRESS,
                        className="input full-width",
                    ),
                ],
            ),
            html.Div(
                className="input-group",
                children=[
                    html.Label("Staking Pool Member Address:", className="label"),
                    html.Div(
                        style={"display": "flex", "align-items": "center"},
                        children=[
                            dcc.Input(
                                id="get-member-user-address-input",
                                type="text",
                                value=DEFAULT_GET_MEMBER_USER_ADDRESS,
                                className="input full-width",
                            ),
                            html.Span(
                                "?",
                                id="tooltip-trigger-2",
                                className="tooltip-trigger",
                                n_clicks=0,
                            ),
                        ],
                    ),
                    html.Div(
                        id="tooltip-content-2",
                        className="tooltip-content",
                        style={"display": "none"},
                        children=[
                            html.P(
                                "Addresses used on the TON Whales Staking Stats Page"
                            ),
                            html.P(
                                "Please check and enter the address in the following way:"
                            ),
                            html.Ol(
                                [
                                    html.Li(
                                        [
                                            "Access the TON Whales Staking page ",
                                            html.A(
                                                "https://tonwhales.com/staking",
                                                href="https://tonwhales.com/staking",
                                                target="_blank",
                                                rel="noopener noreferrer",
                                            ),
                                        ]
                                    ),
                                    html.Li(
                                        'Connect to Wallet Connect with your staking Wallet and press "Next" under Check your staking balance to access the Staking Stats page.'
                                    ),
                                    html.Li(
                                        "Go to Details in Your Pools and activate developer mode (F12)"
                                    ),
                                    html.Li(
                                        "Check the GET request for the get_member command in the Network tab of the developer tools"
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="flex-container",
                children=[
                    html.Div(
                        style={
                            "flex": "1",
                            "margin-right": "10px",
                            "position": "relative",
                        },
                        children=[
                            html.Label("Timezone Offset:", className="label"),
                            html.Div(
                                style={"display": "flex", "align-items": "center"},
                                children=[
                                    dcc.Input(
                                        id="adjust-val-input",
                                        type="number",
                                        value=DEFAULT_TIMEZONE_OFFSET,
                                        className="input small-input",
                                    ),
                                    html.Span(
                                        "?",
                                        id="tooltip-trigger",
                                        className="tooltip-trigger",
                                        n_clicks=0,
                                    ),
                                    html.Div(
                                        id="tooltip-content",
                                        className="tooltip-content",
                                        style={"display": "none"},
                                        children=[
                                            html.P(
                                                "This value is used to calculate staking reward data."
                                            ),
                                            html.P(
                                                "Ton transactions do not have a schema for recording individual staking reward data for each stake source address. Therefore, staking reward data is calculated and generated from the stake originator's balance obtained from the block information."
                                            ),
                                            html.P(
                                                "Specifically, the difference between the balances corresponding to seqno (N-1) and seqno (N) in a particular acquisition range is calculated, and if the value is above the threshold, the reward is considered granted."
                                            ),
                                            html.P(
                                                "The amount of reward depends on the number of stakes. Please change Timezone Offset to match the value of Amount on the graph."
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    html.Div(
                        style={"flex": "1", "margin-right": "10px"},
                        children=[
                            html.Label("Hour (0-23):", className="label"),
                            dcc.Input(
                                id="hour-input",
                                type="number",
                                min=0,
                                max=23,
                                step=1,
                                value=DEFAULT_DAILY_FETCH_HOUR,
                                className="input small-input",
                            ),
                        ],
                    ),
                    html.Div(
                        style={"flex": "2"},
                        children=[
                            html.Label("Date Range:", className="label"),
                            dcc.DatePickerRange(
                                id="date-picker-range",
                                start_date=datetime.now(TZ).date() - timedelta(days=30),
                                end_date=datetime.now(TZ).date(),
                                display_format="YYYY-MM-DD",
                                className="date-picker",
                            ),
                        ],
                    ),
                ],
            ),
            html.Div(
                className="button-container",
                children=[
                    html.Button(
                        "Fetch Data", id="fetch-data-button", className="button"
                    ),
                    html.Button(
                        "Go Staking Stats",
                        id="go-staking-stats-button",
                        className="secondary-button",
                    ),
                ],
            ),
            html.Div(
                className="graph-container",
                children=[
                    dcc.Loading(
                        id="loading-1",
                        type="default",
                        children=[dcc.Graph(id="staking-graph")],
                    ),
                ],
            ),
            html.Div(
                style={
                    "display": "flex",
                    "justify-content": "space-between",
                    "align-items": "center",
                    "margin-top": "20px",
                },
                children=[
                    dcc.Dropdown(
                        id="data-selector",
                        options=[
                            {"label": "All Data", "value": "all"},
                            {"label": "Staked Amount Only", "value": "staked"},
                        ],
                        value="all",
                        className="dropdown",
                    ),
                    html.Button(
                        "Save Staking Reward History",
                        id="generate-reward-history-button",
                        className="button",
                    ),
                ],
            ),
            html.Div(
                id="output-message",
                style={
                    "margin-top": "20px",
                    "text-align": "center",
                    "font-weight": "bold",
                },
            ),
            dcc.ConfirmDialog(
                id="confirm-overwrite",
                message="File already exists. Do you want to overwrite it?",
            ),
            dcc.Store(id="staking-data-store"),
            html.Div(id="dummy-output", style={"display": "none"}),
        ],
    )


app.layout = create_layout()


@app.callback(
    [Output("staking-data-store", "data"), Output("output-message", "children")],
    Input("fetch-data-button", "n_clicks"),
    [
        State("pool-address-input", "value"),
        State("get-member-user-address-input", "value"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date"),
        State("hour-input", "value"),
    ],
    prevent_initial_call=True,
)
def fetch_data(
    n_clicks: Optional[int],
    pool_address: str,
    get_member_user_address: str,
    start_date: str,
    end_date: str,
    hour: int,
) -> Tuple[Optional[List[Dict[str, Any]]], str]:
    """
    Fetch staking data based on user inputs.

    Args:
        n_clicks (Optional[int]): Number of times the fetch button was clicked.
        pool_address (str): Address of the staking pool.
        get_member_user_address (str): Address of the user to query.
        start_date (str): Start date for fetching data.
        end_date (str): End date for fetching data.
        hour (int): Hour of the day to fetch data for.

    Returns:
        Tuple[Optional[List[Dict[str, Any]]], str]: Fetched data and status message.
    """
    if n_clicks is None:
        return dash.no_update, dash.no_update

    try:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=TZ)
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=TZ)
        hour = int(hour)
        if hour < 0 or hour > 23:
            raise ValueError("Hour must be between 0 and 23")

        history = asyncio.run(
            get_staking_history(
                start_datetime,
                end_datetime,
                hour,
                pool_address,
                get_member_user_address,
            )
        )

        if not history:
            return (
                None,
                "Error: No staking history data retrieved. Please check the input parameters and try again.",
            )

        df = pd.DataFrame(history)
        message = f"Data fetched successfully. {len(df)} records retrieved."

        if SAVE_ALLOW_STKRWD:
            try:
                d_today = datetime.today().date()
                num = len(df)
                output_dir = Path(__file__).parent / "output"
                output_dir.mkdir(exist_ok=True)
                csv_file_path = (
                    output_dir
                    / f"ton_whales_staking_amount_history_N={num}_{d_today}.csv"
                )
                df.to_csv(
                    csv_file_path, index=False, quoting=csv.QUOTE_NONE, escapechar="\\"
                )
                message += f" Data saved to {csv_file_path}"
            except Exception as save_error:
                message += f" Error saving data: {str(save_error)}"

        return df.to_dict("records"), message
    except Exception as e:
        return None, f"Error: {str(e)}"


@app.callback(
    Output("output-message", "children", allow_duplicate=True),
    Input("go-staking-stats-button", "n_clicks"),
    prevent_initial_call=True,
)
def open_staking_stats(n_clicks: Optional[int]) -> str:
    """
    Open TON Whales Staking Stats page in a new browser tab.

    Args:
        n_clicks (Optional[int]): Number of times the button was clicked.

    Returns:
        str: Status message.
    """
    if n_clicks is not None:
        url = f"https://tonwhales.com/staking/address/{BASIC_WORKCHAIN_ADDRESS}"
        webbrowser.open(url)
        return "Opened TON Whales Staking Stats page in a new browser tab."
    return "No action taken."


@app.callback(
    Output("staking-graph", "figure"),
    Input("staking-data-store", "data"),
    Input("data-selector", "value"),
    State("hour-input", "value"),
)
def update_graph(
    data: Optional[List[Dict[str, Any]]], selected_data: str, hour: int
) -> go.Figure:
    """
    Update the staking graph based on fetched data and user selection.

    Args:
        data (Optional[List[Dict[str, Any]]]): Fetched staking data.
        selected_data (str): User-selected data type to display.
        hour (int): Hour of the day for x-axis formatting.

    Returns:
        go.Figure: Updated Plotly figure object.
    """
    if data is None:
        return go.Figure()

    df = pd.DataFrame(data)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])

    if selected_data == "all":
        fig = go.Figure()
        for column in [
            "Staked Amount",
            "Pending Deposit",
            "Pending Withdraw",
            "Withdraw Available",
        ]:
            fig.add_trace(
                go.Scatter(
                    x=df["Timestamp"], y=df[column], name=column, mode="lines+markers"
                )
            )
    else:
        fig = go.Figure(
            go.Scatter(
                x=df["Timestamp"],
                y=df["Staked Amount"],
                name="Staked Amount",
                mode="lines+markers",
            )
        )

    hour_str = f"{int(hour):02d}"  # Ensure two-digit format
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Amount",
        xaxis=dict(
            tickformat=f"%Y-%m-%d {hour_str}:%M:%S",
            tickmode="auto",
            nticks=20,
        ),
        hovermode="x unified",
    )

    fig.update_traces(hovertemplate=f"%{{x|%Y-%m-%d {hour_str}:%M:%S}}<br>%{{y:.2f}}")

    return fig


@app.callback(
    Output("confirm-overwrite", "displayed"),
    Output("output-message", "children", allow_duplicate=True),
    Input("generate-reward-history-button", "n_clicks"),
    [
        State("staking-data-store", "data"),
        State("adjust-val-input", "value"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date"),
    ],
    prevent_initial_call=True,
)
def generate_reward_history(
    n_clicks: Optional[int],
    data: Optional[List[Dict[str, Any]]],
    adjust_val: float,
    start_date: str,
    end_date: str,
) -> Tuple[bool, str]:
    """
    Generate and save staking reward history.

    Args:
        n_clicks (Optional[int]): Number of times the button was clicked.
        data (Optional[List[Dict[str, Any]]]): Fetched staking data.
        adjust_val (float): Adjustment value for reward calculation.
        start_date (str): Start date of the data range.
        end_date (str): End date of the data range.

    Returns:
        Tuple[bool, str]: Whether to display overwrite confirmation and status message.
    """
    if n_clicks is None or data is None:
        return False, ""

    df = pd.DataFrame(data)
    reward_df = calculate_staking_rewards(df, float(adjust_val))
    d_today = datetime.today().date()
    num = len(reward_df)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    filename = f"staking_history_{start_date}_to_{end_date}_adj{adjust_val}_N{num}_{d_today}.csv"
    csv_file_path = output_dir / filename

    if csv_file_path.exists():
        return True, ""

    reward_df.to_csv(
        csv_file_path, index=False, quoting=csv.QUOTE_NONE, escapechar="\\"
    )
    return False, f"Staking compensation history is saved in {csv_file_path}."


@app.callback(
    Output("output-message", "children", allow_duplicate=True),
    Input("confirm-overwrite", "submit_n_clicks"),
    [
        State("staking-data-store", "data"),
        State("adjust-val-input", "value"),
        State("date-picker-range", "start_date"),
        State("date-picker-range", "end_date"),
    ],
    prevent_initial_call=True,
)
def handle_overwrite_confirmation(
    submit_n_clicks: Optional[int],
    data: Optional[List[Dict[str, Any]]],
    adjust_val: float,
    start_date: str,
    end_date: str,
) -> str:
    """
    Handle confirmation for overwriting existing reward history file.

    Args:
        submit_n_clicks (Optional[int]): Number of times the confirmation button was clicked.
        data (Optional[List[Dict[str, Any]]]): Fetched staking data.
        adjust_val (float): Adjustment value for reward calculation.
        start_date (str): Start date of the data range.
        end_date (str): End date of the data range.

    Returns:
        str: Status message.
    """
    if submit_n_clicks is None or data is None:
        return ""

    df = pd.DataFrame(data)
    reward_df = calculate_staking_rewards(df, float(adjust_val))
    d_today = datetime.today().date()
    num = len(reward_df)

    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    filename = f"staking_history_{start_date}_to_{end_date}_adj{adjust_val}_N{num}_{d_today}.csv"
    csv_file_path = output_dir / filename

    reward_df.to_csv(
        csv_file_path, index=False, quoting=csv.QUOTE_NONE, escapechar="\\"
    )
    return f"Staking compensation history is saved in {csv_file_path}."


if __name__ == "__main__":
    app.run_server(debug=True)
