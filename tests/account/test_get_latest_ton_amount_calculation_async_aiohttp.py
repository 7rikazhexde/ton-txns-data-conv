import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from aiohttp import ClientError, ClientResponseError, ClientSession
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import (
    get_latest_ton_amount_calculation_async_aiohttp as glta,
)


@pytest.fixture
def mock_aiohttp_session(mocker: MockerFixture) -> MockerFixture:
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    return mock_session


@pytest.mark.asyncio
async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
    mock_response = mocker.AsyncMock()
    mock_response.raise_for_status.side_effect = ClientResponseError(
        request_info=mocker.Mock(),
        history=mocker.Mock(),
        status=404,
        message="Not Found",
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ClientResponseError):
        await glta.fetch_data(mock_session, "https://example.com")


@pytest.mark.asyncio
async def test_get_latest_block(
    mock_aiohttp_session: MockerFixture, mocker: MockerFixture
) -> None:
    mock_response = {
        "last": {"seqno": 12345},
        "now": 1628097600,
    }
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        return_value=mock_response,
    )

    result = await glta.get_latest_block(mock_aiohttp_session)

    assert result[0] == 12345
    assert isinstance(result[1], datetime)
    assert isinstance(result[2], datetime)


@pytest.mark.asyncio
async def test_get_staking_info_success(mocker: MockerFixture) -> None:
    mock_data = {
        "result": [
            {"value": "1000000000000"},
            {"value": "2000000000000"},
            {"value": "3000000000000"},
            {"value": "4000000000000"},
        ]
    }
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        return_value=mock_data,
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    result = await glta.get_staking_info(
        mock_session, seqno, timestamp, pool_address, get_member_user_address
    )

    assert result is not None
    assert result["Seqno"] == seqno
    assert result["Total Staked Amount"] == 10000.0


@pytest.mark.asyncio
async def test_get_staking_info_no_data(mocker: MockerFixture) -> None:
    mock_data: Dict[str, List[Any]] = {"result": []}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        return_value=mock_data,
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    seqno = 12345
    timestamp = datetime.now(timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    result = await glta.get_staking_info(
        mock_session, seqno, timestamp, pool_address, get_member_user_address
    )

    assert result is None


@pytest.mark.asyncio
async def test_ton_rate_by_ticker(mocker: MockerFixture) -> None:
    mock_data = {"rates": {"TON": {"prices": {"JPY": "200.5"}}}}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        return_value=mock_data,
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    result = await glta.ton_rate_by_ticker(mock_session)

    assert result == 200.5


@pytest.mark.asyncio
async def test_get_ton_balance(mocker: MockerFixture) -> None:
    mock_data = {"balance": "1500000000"}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        return_value=mock_data,
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    result = await glta.get_ton_balance(mock_session, user_friendly_address)

    assert result == 1.5


@pytest.mark.asyncio
async def test_on_request_start(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        True,
    )
    mock_params = type("MockParams", (), {"url": "https://example.com"})()
    await glta.on_request_start(None, None, mock_params)
    captured = capsys.readouterr()
    assert "Sending request: https://example.com" in captured.out


@pytest.mark.asyncio
async def test_on_request_end(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        True,
    )
    mock_params = type(
        "MockParams", (), {"response": type("MockResponse", (), {"status": 200})()}
    )()
    await glta.on_request_end(None, None, mock_params)
    captured = capsys.readouterr()
    assert "Received response: 200" in captured.out


@pytest.mark.asyncio
async def test_create_trace_config() -> None:
    trace_config = glta.create_trace_config(True)
    assert trace_config is not None
    assert len(trace_config.on_request_start) == 1
    assert len(trace_config.on_request_end) == 1

    trace_config = glta.create_trace_config(False)
    assert trace_config is None


@pytest.mark.asyncio
async def test_main_success(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now()),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_staking_info",
        return_value={"Timestamp": "2023-01-01 21:00:00", "Total Staked Amount": 100.0},
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_ton_balance",
        return_value=50.0,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ton_rate_by_ticker",
        return_value=2.0,
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "seqno: 12345" in captured.out
    assert "My account hold TON price:" in captured.out


@pytest.mark.asyncio
async def test_main_no_staking_info(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now()),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_staking_info",
        return_value=None,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_ton_balance",
        return_value=50.0,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ton_rate_by_ticker",
        return_value=2.0,
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Failed to get staking info." in captured.out


@pytest.mark.asyncio
async def test_main_http_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=ClientResponseError(
            request_info=mocker.Mock(),
            history=mocker.Mock(),
            status=404,
            message="Not Found",
        ),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "HTTP error occurred: 404 - Not Found" in captured.out


@pytest.mark.asyncio
async def test_main_network_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=ClientError("Network Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Network error occurred: Network Error" in captured.out


@pytest.mark.asyncio
async def test_main_timeout_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=asyncio.TimeoutError(),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Request timed out" in captured.out


@pytest.mark.asyncio
async def test_main_unexpected_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=Exception("Unexpected Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out
