import asyncio
import gzip
from datetime import datetime, timezone
from typing import Any, Dict, List

import aiohttp
import pytest
from aiohttp import ClientError, ClientResponseError, ClientSession, TraceConfig
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import (
    get_latest_ton_amount_calculation_async_aiohttp as glta,
)


@pytest.fixture
def mock_config(mocker: MockerFixture) -> Dict[str, Any]:
    return {
        "ton_info": {
            "user_friendly_address": "EQCkR1cGmnsE45N4K0otPl5EnxnRakmGqeJUNua5fkWhales",
            "pool_address": "EQA_zaBwynX7yc0XCx2qnpUI71wv7mjmSVcogHw0mNAt6cgv",
            "get_member_use_address": "EQCkR1cGmnsE45N4K0otPl5EnxnRakmGqeJUNua5fkWhales",
        },
        "staking_info": {
            "local_timezone": 9,
        },
        "cryptact_info": {
            "counter": "JPY",
        },
        "debug_info": {
            "enable_tracing": False,
        },
    }


@pytest.fixture
def mock_aiohttp_session(mocker: MockerFixture) -> MockerFixture:
    """
    aiohttp.ClientSession のモックを提供するフィクスチャ

    :param mocker: pytestのモッカー
    :return: モックされた ClientSession
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    return mock_session


def test_initialize_address_success(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    initialize_address 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
    glta.initialize_address()
    assert (
        glta.BASIC_WORKCHAIN_ADDRESS == mock_config["ton_info"]["user_friendly_address"]
    )
    assert glta.DEFAULT_UF_ADDRESS == mock_config["ton_info"]["user_friendly_address"]


def test_initialize_address_failure(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    initialize_address 関数がエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    """
    invalid_config = mock_config.copy()
    invalid_config["ton_info"]["user_friendly_address"] = ""
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        invalid_config,
    )

    with pytest.raises(SystemExit) as excinfo:
        glta.initialize_address()
    assert excinfo.value.code == 1


@pytest.mark.asyncio
async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が HTTP エラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 404
    mock_response.reason = "Not Found"
    mock_response.headers = {
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
    }
    mock_response.read = mocker.AsyncMock(return_value=b'{"error": "Not Found"}')

    mock_request_info = mocker.Mock()
    mock_history = mocker.Mock()
    mock_response.request_info = mock_request_info
    mock_response.history = mock_history

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ClientResponseError) as exc_info:
        await glta.fetch_data(mock_session, "https://example.com")

    assert exc_info.value.status == 404
    assert "Not Found" in str(exc_info.value)

    mock_session.get.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_fetch_data_gzip_success(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が gzip 圧縮されたデータを正常に解凍できることをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Encoding": "gzip"}
    mock_response.read = mocker.AsyncMock(
        return_value=gzip.compress(b'{"key": "value"}')
    )

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_fetch_data_gzip_failure(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が gzip 圧縮と表示されているが実際には圧縮されていないデータを適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Encoding": "gzip"}
    mock_response.read = mocker.AsyncMock(return_value=b'{"key": "value"}')

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_fetch_data_non_gzip(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が非 gzip 圧縮データを正しく処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.read = mocker.AsyncMock(return_value=b'{"key": "value"}')

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_fetch_data_invalid_json(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が無効な JSON 形式のデータを適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.read = mocker.AsyncMock(return_value=b'["This", "is", "a", "list"]')

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ValueError, match="Expected a JSON object, got list"):
        await glta.fetch_data(mock_session, "https://example.com")

    mock_session.get.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_get_latest_block(
    mock_aiohttp_session: MockerFixture, mocker: MockerFixture
) -> None:
    """
    get_latest_block 関数が正しく動作することをテストする

    :param mock_aiohttp_session: モックされた aiohttp セッション
    :param mocker: pytestのモッカー
    """
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
    """
    get_staking_info 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
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
    """
    get_staking_info 関数がデータ不足の場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
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
    """
    ton_rate_by_ticker 関数が正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
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
    """
    get_ton_balance 関数が正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
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
    """
    on_request_start 関数が正しくリクエスト開始をログに記録することをテストする

    :param capsys: 標準出力をキャプチャするフィクスチャ
    :param mocker: pytestのモッカー
    """
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
    """
    on_request_end 関数が正しくリクエスト終了をログに記録することをテストする

    :param capsys: 標準出力をキャプチャするフィクスチャ
    :param mocker: pytestのモッカー
    """
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


def test_create_trace_config() -> None:
    """
    create_trace_config 関数が正しく動作することをテストする
    """
    trace_config = glta.create_trace_config(True)
    assert trace_config is not None
    assert len(trace_config.on_request_start) == 1
    assert len(trace_config.on_request_end) == 1

    trace_config = glta.create_trace_config(False)
    assert trace_config is None


@pytest.mark.asyncio
async def test_main_success(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
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
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数がステーキング情報なしの場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
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
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数が HTTP エラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
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
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数がネットワークエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=ClientError("Network Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Network error occurred: Network Error" in captured.out


@pytest.mark.asyncio
async def test_main_timeout_error(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数がタイムアウトエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=asyncio.TimeoutError(),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Request timed out" in captured.out


@pytest.mark.asyncio
async def test_main_unexpected_error(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数が予期しないエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=Exception("Unexpected Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_main_with_trace_config(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    main 関数がトレース設定を正しく使用することをテストする（enable_tracing = True）

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    """
    config_with_tracing = mock_config.copy()
    config_with_tracing["debug_info"] = {"enable_tracing": True}

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        config_with_tracing,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        True,
    )

    mock_client_session = mocker.patch("aiohttp.ClientSession")
    mock_create_trace_config = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.create_trace_config"
    )
    mock_trace_config = mocker.Mock(spec=TraceConfig)
    mock_create_trace_config.return_value = mock_trace_config

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        return_value=(1, datetime.now(), datetime.now()),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_staking_info",
        return_value=None,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_ton_balance",
        return_value=0,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ton_rate_by_ticker",
        return_value=0,
    )

    await glta.main()

    mock_create_trace_config.assert_called_once_with(True)
    mock_client_session.assert_called_once()

    _, kwargs = mock_client_session.call_args
    assert isinstance(kwargs["connector"], aiohttp.TCPConnector)
    assert kwargs["connector"].limit == 10
    assert kwargs["connector"].force_close
    assert kwargs["timeout"].total == 10
    assert kwargs["timeout"].connect == 5
    assert kwargs["auto_decompress"]
    assert "trace_configs" in kwargs
    assert kwargs["trace_configs"] == [mock_trace_config]


@pytest.mark.asyncio
async def test_main_without_trace_config(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    main 関数がトレース設定なしで正しく動作することをテストする（enable_tracing = False）

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    """
    config_without_tracing = mock_config.copy()
    config_without_tracing["debug_info"] = {"enable_tracing": False}

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.config",
        config_without_tracing,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        False,
    )

    mock_client_session = mocker.patch("aiohttp.ClientSession")
    mock_create_trace_config = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.create_trace_config"
    )
    mock_create_trace_config.return_value = None

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        return_value=(1, datetime.now(), datetime.now()),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_staking_info",
        return_value=None,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_ton_balance",
        return_value=0,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ton_rate_by_ticker",
        return_value=0,
    )

    await glta.main()

    mock_create_trace_config.assert_called_once_with(False)
    mock_client_session.assert_called_once()

    _, kwargs = mock_client_session.call_args
    assert isinstance(kwargs["connector"], aiohttp.TCPConnector)
    assert kwargs["connector"].limit == 10
    assert kwargs["connector"].force_close
    assert kwargs["timeout"].total == 10
    assert kwargs["timeout"].connect == 5
    assert kwargs["auto_decompress"]
    assert "trace_configs" not in kwargs
