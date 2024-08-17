import asyncio
import gzip
import json
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp
import pytest
from aiohttp import (
    ClientResponse,
    ClientResponseError,
    ClientSession,
    ClientTimeout,
    TCPConnector,
)
from pytest_mock import MockerFixture

import ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp as glta
from ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp import (
    TraceConfig,
)


@pytest.fixture
def mock_config(mocker: MockerFixture) -> Dict[str, Any]:
    """
    モックされた設定データを提供するフィクスチャ。

    :param mocker: pytest-mockのMockerFixture
    :return: テスト用の設定データを含む辞書
    """
    return {
        "ton_info": {
            "user_friendly_address": "test_user_friendly_address",
            "pool_address": "test_pool_address",
            "get_member_use_address": "test_get_member_use_address",
        },
        "staking_info": {"local_timezone": 9},
        "cryptact_info": {"counter": "JPY"},
        "debug_info": {"enable_tracing": True},
    }


@pytest.fixture(autouse=True)
def mock_address(mocker: MockerFixture) -> None:
    """
    Addressクラスをモックするフィクスチャ。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_address = mocker.Mock()
    mock_address.to_str.return_value = "mocked_address"
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.Address",
        return_value=mock_address,
    )


@pytest.fixture(autouse=True)
def mock_load_config(mocker: MockerFixture, mock_config: Dict[str, Any]) -> None:
    """
    load_config関数をモックするフィクスチャ。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    """
    mocker.patch.object(glta, "load_config", return_value=mock_config)


def test_initialize_address_success(
    mock_config: Dict[str, Any], mocker: MockerFixture
) -> None:
    """
    initialize_address関数の成功ケースをテストする。

    :param mock_config: モックされた設定データ
    :param mocker: pytest-mockのMockerFixture
    """
    mocker.patch.object(glta, "config", mock_config)
    glta.initialize_address()
    assert glta.DEFAULT_UF_ADDRESS == "test_user_friendly_address"
    assert glta.BASIC_WORKCHAIN_ADDRESS == "mocked_address"


def test_initialize_address_failure(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    initialize_address関数の失敗ケースをテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    """
    invalid_config = mock_config.copy()
    invalid_config["ton_info"]["user_friendly_address"] = ""
    mocker.patch.object(glta, "config", invalid_config)
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.Address",
        side_effect=glta.AddressError("Test error"),
    )

    with pytest.raises(SystemExit) as excinfo:
        glta.initialize_address()
    assert excinfo.value.code == 1


@pytest.mark.asyncio
async def test_fetch_data(mocker: MockerFixture) -> None:
    """
    fetch_data関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_response = mocker.AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.read.return_value = b'{"key": "value"}'
    mock_response.headers = {}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_fetch_data_gzip(mocker: MockerFixture) -> None:
    """
    gzip圧縮されたデータに対するfetch_data関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_response = mocker.AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.read.return_value = gzip.compress(b'{"key": "gzip_value"}')
    mock_response.headers = {"Content-Encoding": "gzip"}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "gzip_value"}


@pytest.mark.asyncio
async def test_fetch_data_invalid_gzip(mocker: MockerFixture) -> None:
    """
    無効なgzipデータに対するfetch_data関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_response = mocker.AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.read.return_value = b"Invalid gzip data"
    mock_response.headers = {"Content-Encoding": "gzip"}
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(json.JSONDecodeError):
        await glta.fetch_data(mock_session, "https://example.com")


@pytest.mark.asyncio
async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
    """
    HTTPエラーが発生した場合のfetch_data関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_response = mocker.AsyncMock(spec=ClientResponse)
    mock_response.status = 404
    mock_response.reason = "Not Found"
    mock_response.request_info = mocker.Mock()
    mock_response.history = ()
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ClientResponseError):
        await glta.fetch_data(mock_session, "https://example.com")


@pytest.mark.asyncio
async def test_fetch_data_non_dict_json(mocker: MockerFixture) -> None:
    """
    JSONレスポンスが辞書でない場合のfetch_data関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_response = mocker.AsyncMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.read.return_value = b"[1, 2, 3]"  # リストを返すJSON
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ValueError) as excinfo:
        await glta.fetch_data(mock_session, "https://example.com")

    assert "Expected a JSON object, got list" in str(excinfo.value)


@pytest.mark.asyncio
async def test_get_latest_block(mocker: MockerFixture) -> None:
    """
    get_latest_block関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch.object(
        glta, "fetch_data", return_value={"last": {"seqno": 12345}, "now": 1628097600}
    )

    result = await glta.get_latest_block(mock_session)
    assert result[0] == 12345
    assert isinstance(result[1], datetime)
    assert isinstance(result[2], datetime)


@pytest.mark.asyncio
async def test_get_staking_info(mocker: MockerFixture) -> None:
    """
    get_staking_info関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch.object(
        glta,
        "fetch_data",
        return_value={
            "result": [
                {"value": "1000000000"},
                {"value": "2000000000"},
                {"value": "3000000000"},
                {"value": "4000000000"},
            ]
        },
    )

    result = await glta.get_staking_info(
        mock_session,
        12345,
        datetime.now(timezone.utc),
        "test_pool_address",
        "test_get_member_use_address",
    )
    assert result is not None
    assert result["Total Staked Amount"] == 10.0


@pytest.mark.asyncio
async def test_get_staking_info_no_result(mocker: MockerFixture) -> None:
    """
    ステーキング情報が取得できない場合のget_staking_info関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch.object(glta, "fetch_data", return_value={})

    result = await glta.get_staking_info(
        mock_session,
        12345,
        datetime.now(timezone.utc),
        "test_pool_address",
        "test_get_member_use_address",
    )
    assert result is None


@pytest.mark.asyncio
async def test_ton_rate_by_ticker(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch.object(
        glta,
        "fetch_data",
        return_value={"rates": {"TON": {"prices": {"JPY": "200.5"}}}},
    )

    result = await glta.ton_rate_by_ticker(mock_session)
    assert result == 200.5


@pytest.mark.asyncio
async def test_get_ton_balance(mocker: MockerFixture) -> None:
    """
    get_ton_balance関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch.object(
        glta,
        "fetch_data",
        return_value={"balance": "1500000000"},
    )

    result = await glta.get_ton_balance(mock_session, "test_user_friendly_address")
    assert result == 1.5


@pytest.mark.asyncio
async def test_main_success(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main関数の成功ケースをテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(
        glta,
        "get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now(timezone.utc)),
    )
    mocker.patch.object(
        glta,
        "get_staking_info",
        return_value={"Total Staked Amount": 100.0, "Timestamp": "2023-01-01 00:00:00"},
    )
    mocker.patch.object(glta, "get_ton_balance", return_value=50.0)
    mocker.patch.object(glta, "ton_rate_by_ticker", return_value=2.0)

    await glta.main()

    captured = capsys.readouterr()
    assert "Total Staked Amount: 100.000000000" in captured.out
    assert "Balance: 50.000000000" in captured.out
    assert "Hold TON: 150.000000000" in captured.out
    assert "Rate: 2.00" in captured.out


@pytest.mark.asyncio
async def test_main_no_staking_info(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    ステーキング情報がない場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(
        glta,
        "get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now(timezone.utc)),
    )
    mocker.patch.object(glta, "get_staking_info", return_value=None)
    mocker.patch.object(glta, "get_ton_balance", return_value=50.0)
    mocker.patch.object(glta, "ton_rate_by_ticker", return_value=2.0)

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
    HTTPエラーが発生した場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(
        glta,
        "get_latest_block",
        side_effect=ClientResponseError(
            request_info=mocker.Mock(), history=(), status=404, message="Not Found"
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
    ネットワークエラーが発生した場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(
        glta, "get_latest_block", side_effect=aiohttp.ClientError("Network Error")
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
    タイムアウトエラーが発生した場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(glta, "get_latest_block", side_effect=asyncio.TimeoutError())

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
    予期せぬエラーが発生した場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "config", mock_config)
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    mocker.patch.object(
        glta, "get_latest_block", side_effect=Exception("Unexpected Error")
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_create_trace_config() -> None:
    """
    create_trace_config関数の動作をテストする。
    """
    trace_config = glta.create_trace_config(True)
    assert trace_config is not None
    assert len(trace_config.on_request_start) == 1
    assert len(trace_config.on_request_end) == 1

    trace_config = glta.create_trace_config(False)
    assert trace_config is None


@pytest.mark.asyncio
async def test_on_request_start(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    """
    on_request_start関数の動作をテストする。

    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    :param mocker: pytest-mockのMockerFixture
    """
    params = mocker.Mock(spec=glta.TraceRequestStartParams)
    params.url = "https://example.com"
    await glta.on_request_start(None, None, params)
    captured = capsys.readouterr()
    assert "Sending request: https://example.com" in captured.out


@pytest.mark.asyncio
async def test_on_request_end(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    """
    on_request_end関数の動作をテストする。

    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    :param mocker: pytest-mockのMockerFixture
    """
    params = mocker.Mock(spec=glta.TraceRequestEndParams)
    params.response = mocker.Mock()
    params.response.status = 200
    await glta.on_request_end(None, None, params)
    captured = capsys.readouterr()
    assert "Received response: 200" in captured.out


@pytest.mark.asyncio
async def test_main_no_trace_config(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    トレース設定がない場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    config_without_tracing = mock_config.copy()
    config_without_tracing["debug_info"] = {"enable_tracing": False}
    mocker.patch.object(glta, "config", config_without_tracing)
    mocker.patch.object(glta, "ENABLE_TRACING", False)

    # Mock create_trace_config to return None
    mocker.patch.object(glta, "create_trace_config", return_value=None)

    # Create mock objects for TCPConnector and ClientTimeout
    mock_connector = mocker.Mock(spec=TCPConnector)
    mock_timeout = mocker.Mock(spec=ClientTimeout)

    # Patch the creation of TCPConnector and ClientTimeout in glta module
    mocker.patch.object(glta, "TCPConnector", return_value=mock_connector)
    mocker.patch.object(glta, "ClientTimeout", return_value=mock_timeout)

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_client_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session
    )

    # Mock other necessary functions
    mocker.patch.object(
        glta,
        "get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now(timezone.utc)),
    )
    mocker.patch.object(
        glta,
        "get_staking_info",
        return_value={"Total Staked Amount": 100.0, "Timestamp": "2023-01-01 00:00:00"},
    )
    mocker.patch.object(glta, "get_ton_balance", return_value=50.0)
    mocker.patch.object(glta, "ton_rate_by_ticker", return_value=2.0)

    await glta.main()

    # Check that ClientSession was called with the correct arguments
    mock_client_session.assert_called_once()
    call_kwargs = mock_client_session.call_args[1]
    assert "trace_configs" not in call_kwargs
    assert call_kwargs["connector"] == mock_connector
    assert call_kwargs["timeout"] == mock_timeout
    assert call_kwargs["auto_decompress"] is True

    captured = capsys.readouterr()
    assert "Total Staked Amount: 100.000000000" in captured.out


@pytest.mark.asyncio
async def test_main_with_trace_config(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    トレース設定がある場合のmain関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    config_with_tracing = mock_config.copy()
    config_with_tracing["debug_info"] = {"enable_tracing": True}
    mocker.patch.object(glta, "config", config_with_tracing)
    mocker.patch.object(glta, "ENABLE_TRACING", True)

    # Mock create_trace_config to return a TraceConfig object
    mock_trace_config = mocker.Mock(spec=TraceConfig)
    mocker.patch.object(glta, "create_trace_config", return_value=mock_trace_config)

    # Create mock objects for TCPConnector and ClientTimeout
    mock_connector = mocker.Mock(spec=TCPConnector)
    mock_timeout = mocker.Mock(spec=ClientTimeout)

    # Patch the creation of TCPConnector and ClientTimeout in glta module
    mocker.patch.object(glta, "TCPConnector", return_value=mock_connector)
    mocker.patch.object(glta, "ClientTimeout", return_value=mock_timeout)

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_client_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session
    )

    # Mock other necessary functions
    mocker.patch.object(
        glta,
        "get_latest_block",
        return_value=(12345, datetime.now(timezone.utc), datetime.now(timezone.utc)),
    )
    mocker.patch.object(
        glta,
        "get_staking_info",
        return_value={"Total Staked Amount": 100.0, "Timestamp": "2023-01-01 00:00:00"},
    )
    mocker.patch.object(glta, "get_ton_balance", return_value=50.0)
    mocker.patch.object(glta, "ton_rate_by_ticker", return_value=2.0)

    await glta.main()

    # Check that ClientSession was called with the correct arguments
    mock_client_session.assert_called_once()
    call_kwargs = mock_client_session.call_args[1]
    assert "trace_configs" in call_kwargs
    assert call_kwargs["trace_configs"] == [mock_trace_config]
    assert call_kwargs["connector"] == mock_connector
    assert call_kwargs["timeout"] == mock_timeout
    assert call_kwargs["auto_decompress"] is True

    captured = capsys.readouterr()
    assert "Total Staked Amount: 100.000000000" in captured.out
