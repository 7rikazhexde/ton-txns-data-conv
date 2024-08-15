import platform
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
import pytest
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import get_latest_ton_amount_calculation as glta


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
    }


@pytest.fixture
def mock_httpx_client(mocker: MockerFixture) -> MockerFixture:
    """
    httpx.AsyncClient のモックを提供するフィクスチャ

    :param mocker: pytestのモッカー
    :return: モックされた AsyncClient
    """
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    return mock_client


def test_initialize_address_success(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    initialize_address 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        invalid_config,
    )

    with pytest.raises(SystemExit) as excinfo:
        glta.initialize_address()
    assert excinfo.value.code == 1


@pytest.mark.asyncio
async def test_fetch_data_success(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.json.return_value = {"key": "value"}
    mock_response.raise_for_status.return_value = None

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    result = await glta.fetch_data(mock_client, "https://example.com")

    assert result == {"key": "value"}
    mock_client.get.assert_called_once_with("https://example.com")
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が HTTP エラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "HTTP Error", request=mocker.Mock(), response=mocker.Mock()
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    with pytest.raises(httpx.HTTPStatusError):
        await glta.fetch_data(mock_client, "https://example.com")

    mock_client.get.assert_called_once_with("https://example.com")
    mock_response.raise_for_status.assert_called_once()


@pytest.mark.asyncio
async def test_get_latest_block(
    mock_httpx_client: MockerFixture, mocker: MockerFixture
) -> None:
    """
    get_latest_block 関数が正しく動作することをテストする

    :param mock_httpx_client: モックされた httpx クライアント
    :param mocker: pytestのモッカー
    """
    mock_response = {
        "last": {"seqno": 12345},
        "now": 1628097600,
    }

    mock_fetch_data = mocker.AsyncMock(return_value=mock_response)
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        mock_fetch_data,
    )

    result = await glta.get_latest_block(mock_httpx_client)

    assert result[0] == 12345
    assert isinstance(result[1], datetime)
    assert isinstance(result[2], datetime)

    mock_fetch_data.assert_called_once_with(
        mock_httpx_client, f"{glta.BASE_URL_TONHUB}/block/latest"
    )


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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    result = await glta.get_staking_info(
        mock_client, seqno, timestamp, pool_address, get_member_user_address
    )

    assert result is not None
    assert result["Seqno"] == seqno
    assert result["Timestamp"] == timestamp.astimezone(glta.TZ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    assert result["Staked Amount"] == 1000.0
    assert result["Pending Deposit"] == 2000.0
    assert result["Pending Withdraw"] == 3000.0
    assert result["Withdraw Available"] == 4000.0
    assert result["Total Staked Amount"] == 10000.0


@pytest.mark.asyncio
async def test_get_staking_info_no_result(mocker: MockerFixture) -> None:
    """
    get_staking_info 関数が結果がない場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    mock_data = {"no_result": True}  # "result" キーが存在しないデータ
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    result = await glta.get_staking_info(
        mock_client, seqno, timestamp, pool_address, get_member_user_address
    )

    assert result is None


@pytest.mark.asyncio
async def test_main_no_staking_info(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数がステーキング情報がない場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        mock_config,
    )

    mock_get_latest_block = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block"
    )
    mock_get_latest_block.return_value = (
        12345,
        datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        datetime(2023, 1, 1, 21, 0),
    )

    mock_get_staking_info = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_staking_info"
    )
    mock_get_staking_info.return_value = None  # ステーキング情報がない場合

    mock_get_ton_balance = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_ton_balance"
    )
    mock_get_ton_balance.return_value = 50.0

    mock_ton_rate_by_ticker = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.ton_rate_by_ticker"
    )
    mock_ton_rate_by_ticker.return_value = 2.0

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Failed to get staking info." in captured.out


@pytest.mark.asyncio
async def test_ton_rate_by_ticker_default(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker 関数がデフォルト通貨（JPY）で正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
    mock_data = {"rates": {"TON": {"prices": {"JPY": "200.5"}}}}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    result = await glta.ton_rate_by_ticker(mock_client)

    assert result == 200.5


@pytest.mark.asyncio
async def test_get_ton_balance_success(mocker: MockerFixture) -> None:
    """
    get_ton_balance 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
    mock_data = {"balance": "1500000000"}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    result = await glta.get_ton_balance(mock_client, user_friendly_address)

    assert result == 1.5


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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        mock_config,
    )

    mock_get_latest_block = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block"
    )
    mock_get_latest_block.return_value = (
        12345,
        datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        datetime(2023, 1, 1, 21, 0),
    )

    mock_get_staking_info = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_staking_info"
    )
    mock_get_staking_info.return_value = {
        "Timestamp": "2023-01-01 21:00:00",
        "Total Staked Amount": 100.0,
    }

    mock_get_ton_balance = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_ton_balance"
    )
    mock_get_ton_balance.return_value = 50.0

    mock_ton_rate_by_ticker = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.ton_rate_by_ticker"
    )
    mock_ton_rate_by_ticker.return_value = 2.0

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "seqno: 12345" in captured.out
    assert "Total Staked Amount: 100.000000000" in captured.out
    assert "Balance: 50.000000000" in captured.out
    assert "Hold TON: 150.000000000" in captured.out
    assert "Rate: 2.00" in captured.out
    if platform.system() == "Darwin":
        assert "My account hold TON price: ￥300.00" in captured.out
    else:
        assert "My account hold TON price: ¥300.00" in captured.out


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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        mock_config,
    )

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block",
        side_effect=httpx.HTTPStatusError(
            "HTTP Error",
            request=mocker.Mock(),
            response=mocker.Mock(status_code=404, text="Not Found"),
        ),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "HTTP error occurred: 404 - Not Found" in captured.out


@pytest.mark.asyncio
async def test_tracing_client(
    mocker: MockerFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    """
    TracingClient クラスが正しく動作することをテストする

    :param mocker: pytestのモッカー
    :param capfd: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.ENABLE_TRACING",
        True,
    )
    client = glta.TracingClient()
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request

    mocker.patch.object(httpx.AsyncClient, "send", return_value=mock_response)
    response = await client.send(mock_request)

    assert response == mock_response
    captured = capfd.readouterr()
    assert "Sending request: GET https://example.com" in captured.out
    assert "Received response: 200 from https://example.com" in captured.out


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
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        mock_config,
    )

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block",
        side_effect=httpx.RequestError("Network Error"),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
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
    main 関数が予期しないエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックされた設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.config",
        mock_config,
    )

    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block",
        side_effect=Exception("Unexpected Error"),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_log_request(capfd: pytest.CaptureFixture[str]) -> None:
    """
    log_request 関数が正しくリクエストをログに記録することをテストする

    :param capfd: 標準出力をキャプチャするフィクスチャ
    """
    mock_request = httpx.Request("GET", "https://example.com")
    await glta.log_request(mock_request)
    captured = capfd.readouterr()
    assert "Sending request: GET https://example.com" in captured.out


@pytest.mark.asyncio
async def test_log_response(
    capfd: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    """
    log_response 関数が正しくレスポンスをログに記録することをテストする

    :param capfd: 標準出力をキャプチャするフィクスチャ
    :param mocker: pytestのモッカー
    """
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request
    await glta.log_response(mock_response)
    captured = capfd.readouterr()
    assert "Received response: 200 from https://example.com" in captured.out


@pytest.mark.asyncio
async def test_tracing_client_disabled(mocker: MockerFixture) -> None:
    """
    TracingClient クラスがトレーシングが無効の場合に正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.ENABLE_TRACING",
        False,
    )
    client = glta.TracingClient()
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request

    mocker.patch.object(httpx.AsyncClient, "send", return_value=mock_response)
    response = await client.send(mock_request)

    assert response == mock_response
