import importlib
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
import pytest
from pytest_mock import MockerFixture

import ton_txns_data_conv.account.get_latest_ton_amount_calculation as glta


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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.Address",
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

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.Address",
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
    mock_client = mocker.AsyncMock()
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"key": "value"}
    mock_client.get.return_value = mock_response

    result = await glta.fetch_data(mock_client, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_get_latest_block(mocker: MockerFixture) -> None:
    """
    get_latest_block関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_client = mocker.AsyncMock()
    mocker.patch.object(
        glta, "fetch_data", return_value={"last": {"seqno": 12345}, "now": 1628097600}
    )

    result = await glta.get_latest_block(mock_client)
    assert result[0] == 12345
    assert isinstance(result[1], datetime)
    assert isinstance(result[2], datetime)


@pytest.mark.asyncio
async def test_get_staking_info(mocker: MockerFixture) -> None:
    """
    get_staking_info関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_client = mocker.AsyncMock()
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
        mock_client,
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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "fetch_data", return_value={"no_result": True})

    result = await glta.get_staking_info(
        mock_client,
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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(
        glta,
        "fetch_data",
        return_value={"rates": {"TON": {"prices": {"JPY": "200.5"}}}},
    )

    result = await glta.ton_rate_by_ticker(mock_client)
    assert result == 200.5


@pytest.mark.asyncio
async def test_get_ton_balance(mocker: MockerFixture) -> None:
    """
    get_ton_balance関数の動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_client = mocker.AsyncMock()
    mocker.patch.object(
        glta,
        "fetch_data",
        return_value={"balance": "1500000000"},
    )

    result = await glta.get_ton_balance(mock_client, "test_user_friendly_address")
    assert result == 1.5


# def test_get_currency_symbol_success(mocker):
#    """
#    get_currency_symbolが正常に動作する場合のテスト
#    """
#    mocker.patch(
#        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.DEFAULT_COUNTER_VAL", "USD"
#    )
#    mocker.patch(
#        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_currency_symbol",
#        return_value="$",
#    )
#    mocker.patch(
#        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.Locale",
#        return_value=Locale("en_US"),
#    )
#
#    # symbolを直接再評価
#    symbol = glta.get_currency_symbol(
#        glta.DEFAULT_COUNTER_VAL, locale=glta.Locale("en_US")
#    )
#    assert symbol == "$"


def test_get_currency_symbol_exception_handling(mocker: MockerFixture) -> None:
    """
    get_currency_symbolが例外を発生させた場合のテスト
    """
    # モジュールレベルの変数をパッチ
    mocker.patch.object(glta, "DEFAULT_COUNTER_VAL", "INVALID")

    # get_currency_symbolをモックして例外を発生させる
    mock_get_currency_symbol = mocker.patch("babel.numbers.get_currency_symbol")
    mock_get_currency_symbol.side_effect = ValueError()

    # モジュールを再読み込みして、パッチされた値を反映
    importlib.reload(glta)

    # symbolの値を確認
    assert glta.symbol == "¥"

    # TypeErrorの場合もテスト
    mock_get_currency_symbol.side_effect = TypeError()
    importlib.reload(glta)
    assert glta.symbol == "¥"


# def test_get_currency_symbol_jpy(mocker):
#    """
#    日本円の通貨記号を取得する場合のテスト
#    """
#    mocker.patch('ton_txns_data_conv.account.get_latest_ton_amount_calculation.DEFAULT_COUNTER_VAL', 'JPY')
#    mocker.patch('ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_currency_symbol', return_value='￥')
#    mocker.patch('ton_txns_data_conv.account.get_latest_ton_amount_calculation.Locale', return_value=Locale('ja_JP'))
#
#    # symbolを直接再評価
#    symbol = glta.get_currency_symbol(glta.DEFAULT_COUNTER_VAL, locale=glta.Locale("ja_JP"))
#    assert symbol in ['¥', '￥']  # 半角または全角の円記号を許容


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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "TracingClient", return_value=mock_client)
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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "TracingClient", return_value=mock_client)
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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "TracingClient", return_value=mock_client)
    mocker.patch.object(
        glta,
        "get_latest_block",
        side_effect=httpx.HTTPStatusError(
            "HTTP Error",
            request=mocker.Mock(),
            response=mocker.Mock(status_code=404, text="Not Found"),
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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "TracingClient", return_value=mock_client)
    mocker.patch.object(
        glta, "get_latest_block", side_effect=httpx.RequestError("Network Error")
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Network error occurred: Network Error" in captured.out


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
    mock_client = mocker.AsyncMock()
    mocker.patch.object(glta, "TracingClient", return_value=mock_client)
    mocker.patch.object(
        glta, "get_latest_block", side_effect=Exception("Unexpected Error")
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_log_request(capsys: pytest.CaptureFixture[str]) -> None:
    """
    log_request関数の動作をテストする。

    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mock_request = httpx.Request("GET", "https://example.com")
    await glta.log_request(mock_request)
    captured = capsys.readouterr()
    assert "Sending request: GET https://example.com" in captured.out


@pytest.mark.asyncio
async def test_log_response(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    """
    log_response関数の動作をテストする。

    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    :param mocker: pytest-mockのMockerFixture
    """
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = httpx.Request("GET", "https://example.com")
    await glta.log_response(mock_response)
    captured = capsys.readouterr()
    assert "Received response: 200 from https://example.com" in captured.out


@pytest.mark.asyncio
async def test_tracing_client(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    TracingClientクラスの動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "ENABLE_TRACING", True)
    client = glta.TracingClient()
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request

    mocker.patch.object(httpx.AsyncClient, "send", return_value=mock_response)
    response = await client.send(mock_request)

    assert response == mock_response
    captured = capsys.readouterr()
    assert "Sending request: GET https://example.com" in captured.out
    assert "Received response: 200 from https://example.com" in captured.out


@pytest.mark.asyncio
async def test_tracing_client_disabled(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    トレーシングが無効な場合のTracingClientクラスの動作をテストする。

    :param mocker: pytest-mockのMockerFixture
    :param capsys: 標準出力と標準エラー出力をキャプチャするpytestフィクスチャ
    """
    mocker.patch.object(glta, "ENABLE_TRACING", False)
    client = glta.TracingClient()
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request

    mocker.patch.object(httpx.AsyncClient, "send", return_value=mock_response)
    response = await client.send(mock_request)

    assert response == mock_response
    captured = capsys.readouterr()
    assert captured.out == ""
