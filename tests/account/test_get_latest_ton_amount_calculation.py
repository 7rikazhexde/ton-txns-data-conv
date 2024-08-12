from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
import pytest
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import get_latest_ton_amount_calculation as glta


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


@pytest.mark.asyncio
async def test_fetch_data_success(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
    # モックの応答を設定
    mock_response = mocker.Mock(spec=httpx.Response)
    mock_response.json.return_value = {"key": "value"}
    mock_response.raise_for_status.return_value = None

    # AsyncClientのgetメソッドをモック
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = mock_response

    # fetch_data関数を呼び出し
    result = await glta.fetch_data(mock_client, "https://example.com")

    # アサーション
    assert result == {"key": "value"}
    mock_client.get.assert_called_once_with("https://example.com")
    mock_response.raise_for_status.assert_called_once()


# @pytest.mark.asyncio
# async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
#    """
#    fetch_data 関数が HTTP エラーを適切に処理することをテストする
#
#    :param mocker: pytestのモッカー
#    """
#    # HTTPエラーを発生させるモックを設定
#    mock_response = mocker.Mock(spec=httpx.Response)
#    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
#        "HTTP Error", request=mocker.Mock(), response=mocker.Mock()
#    )
#
#    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
#    mock_client.get.return_value = mock_response
#
#    # エラーが発生することを確認
#    with pytest.raises(httpx.HTTPStatusError):
#        await glta.fetch_data(mock_client, "https://example.com")
#
#    mock_client.get.assert_called_once_with("https://example.com")
#    mock_response.raise_for_status.assert_called_once()


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

    # Mock the fetch_data function
    mock_fetch_data = mocker.AsyncMock(return_value=mock_response)
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        mock_fetch_data,
    )

    result = await glta.get_latest_block(mock_httpx_client)

    assert result[0] == 12345
    assert isinstance(result[1], datetime)
    assert isinstance(result[2], datetime)

    # Verify that fetch_data was called with the correct arguments
    mock_fetch_data.assert_called_once_with(
        mock_httpx_client, f"{glta.BASE_URL_TONHUB}/block/latest"
    )


@pytest.mark.asyncio
async def test_get_staking_info_success(mocker: MockerFixture) -> None:
    """
    get_staking_info 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
    # モックの応答を設定
    mock_data = {
        "result": [
            {"value": "1000000000000"},  # 1000.0
            {"value": "2000000000000"},  # 2000.0
            {"value": "3000000000000"},  # 3000.0
            {"value": "4000000000000"},  # 4000.0
        ]
    }
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    # テスト用のパラメータ
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    # get_staking_info関数を呼び出し
    result = await glta.get_staking_info(
        mock_client, seqno, timestamp, pool_address, get_member_user_address
    )

    # アサーション
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
async def test_get_staking_info_no_data(mocker: MockerFixture) -> None:
    """
    get_staking_info 関数がデータ不足の場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    # データが不足しているモックの応答を設定
    mock_data: Dict[str, List[Any]] = {"result": []}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    # テスト用のパラメータ
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    # get_staking_info関数を呼び出し
    result = await glta.get_staking_info(
        mock_client, seqno, timestamp, pool_address, get_member_user_address
    )

    # アサーション
    assert result is None


@pytest.mark.asyncio
async def test_get_staking_info_fetch_data_call(mocker: MockerFixture) -> None:
    """
    get_staking_info 関数が fetch_data を正しく呼び出すことをテストする

    :param mocker: pytestのモッカー
    """
    # fetch_dataの呼び出しをモック
    mock_fetch_data = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value={"result": []},
    )

    # テスト用のパラメータ
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    seqno = 12345
    timestamp = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    pool_address = "test_pool_address"
    get_member_user_address = "test_member_address"

    # get_staking_info関数を呼び出し
    await glta.get_staking_info(
        mock_client, seqno, timestamp, pool_address, get_member_user_address
    )

    # fetch_dataが正しいURLで呼び出されたことを確認
    expected_url = f"{glta.BASE_URL_TONHUB}/block/{seqno}/{pool_address}/run/get_member/{get_member_user_address}"
    mock_fetch_data.assert_called_once_with(mock_client, expected_url)


@pytest.mark.asyncio
async def test_ton_rate_by_ticker_default(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker 関数がデフォルト通貨（JPY）で正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
    # デフォルト通貨（JPY）のモックデータを設定
    mock_data = {"rates": {"TON": {"prices": {"JPY": "200.5"}}}}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    result = await glta.ton_rate_by_ticker(mock_client)

    assert result == 200.5


@pytest.mark.asyncio
async def test_ton_rate_by_ticker_custom(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker 関数がカスタム通貨（USD）で正しく動作することをテストする

    :param mocker: pytestのモッカー
    """
    # カスタム通貨（USD）のモックデータを設定
    mock_data = {"rates": {"TON": {"prices": {"USD": "1.5"}}}}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    result = await glta.ton_rate_by_ticker(mock_client, "usd")

    assert result == 1.5


@pytest.mark.asyncio
async def test_ton_rate_by_ticker_fetch_data_call(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker 関数が fetch_data を正しく呼び出すことをテストする

    :param mocker: pytestのモッカー
    """
    # fetch_dataの呼び出しをモック
    mock_fetch_data = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value={"rates": {"TON": {"prices": {"JPY": "100"}}}},
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    await glta.ton_rate_by_ticker(mock_client)

    # fetch_dataが正しいURLで呼び出されたことを確認
    expected_url = f"{glta.BASE_URL_TONAPI}/rates?tokens=ton&currencies=ton,jpy"
    mock_fetch_data.assert_called_once_with(mock_client, expected_url)


@pytest.mark.asyncio
async def test_ton_rate_by_ticker_invalid_data(mocker: MockerFixture) -> None:
    """
    ton_rate_by_ticker 関数が無効なデータを適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    # 無効なデータ構造のモックを設定
    mock_data: Dict[str, List[Any]] = {"result": []}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)

    # KeyErrorが発生することを確認
    with pytest.raises(KeyError):
        await glta.ton_rate_by_ticker(mock_client)


@pytest.mark.asyncio
async def test_get_ton_balance_success(mocker: MockerFixture) -> None:
    """
    get_ton_balance 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    """
    # モックの応答を設定 (1.5 TON = 1500000000 nanoTON)
    mock_data = {"balance": "1500000000"}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    result = await glta.get_ton_balance(mock_client, user_friendly_address)

    assert result == 1.5  # 1500000000 nanoTON = 1.5 TON


@pytest.mark.asyncio
async def test_get_ton_balance_fetch_data_call(mocker: MockerFixture) -> None:
    """
    get_ton_balance 関数が fetch_data を正しく呼び出すことをテストする

    :param mocker: pytestのモッカー
    """
    # fetch_dataの呼び出しをモック
    mock_fetch_data = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value={"balance": "1000000000"},
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    await glta.get_ton_balance(mock_client, user_friendly_address)

    # fetch_dataが正しいURLで呼び出されたことを確認
    expected_url = f"{glta.BASE_URL_TONAPI}/accounts/{user_friendly_address}"
    mock_fetch_data.assert_called_once_with(mock_client, expected_url)


@pytest.mark.asyncio
async def test_get_ton_balance_invalid_data(mocker: MockerFixture) -> None:
    """
    get_ton_balance 関数が無効なバランス値を適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    # 無効なデータ構造のモックを設定
    mock_data: Dict[str, Any] = {}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    # KeyErrorが発生することを確認
    with pytest.raises(KeyError):
        await glta.get_ton_balance(mock_client, user_friendly_address)


@pytest.mark.asyncio
async def test_get_ton_balance_invalid_balance(mocker: MockerFixture) -> None:
    """
    get_ton_balance 関数が無効なバランス値を適切に処理することをテストする

    :param mocker: pytestのモッカー
    """
    # 無効なバランス値のモックを設定
    mock_data = {"balance": "invalid"}
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.fetch_data",
        return_value=mock_data,
    )

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    user_friendly_address = "EQtestAbcdefghijklmnopqrstuvwxyz1234567890"

    # ValueError（float()での変換エラー）が発生することを確認
    with pytest.raises(ValueError):
        await glta.get_ton_balance(mock_client, user_friendly_address)


@pytest.mark.asyncio
async def test_main_success(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数が正常に動作することをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    # モックの設定
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

    # main関数の実行
    await glta.main()

    # 出力の確認
    captured = capsys.readouterr()
    assert "seqno: 12345" in captured.out
    assert "Total Staked Amount: 100.000000000" in captured.out
    assert "Balance: 50.000000000" in captured.out
    assert "Hold TON: 150.000000000" in captured.out
    assert "Rate: 2.00" in captured.out
    assert "My account hold TON price: ¥300.00" in captured.out


@pytest.mark.asyncio
async def test_main_no_staking_info(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数がステーキング情報なしの場合に適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    # モックの設定
    mock_get_latest_block = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block"
    )
    mock_get_latest_block.return_value = (
        12345,
        datetime.now(timezone.utc),
        datetime.now(),
    )

    mock_get_staking_info = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_staking_info"
    )
    mock_get_staking_info.return_value = None

    mock_get_ton_balance = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_ton_balance"
    )
    mock_get_ton_balance.return_value = 50.0

    mock_ton_rate_by_ticker = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.ton_rate_by_ticker"
    )
    mock_ton_rate_by_ticker.return_value = 2.0

    mock_tracing_client = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )
    mock_tracing_client.return_value.__aenter__.return_value = mocker.AsyncMock()

    # グローバル変数のモック
    mocker.patch.object(glta, "DEFAULT_POOL_ADDRESS", "mock_pool_address")
    mocker.patch.object(glta, "DEFAULT_GET_MEMBER_USER_ADDRESS", "mock_member_address")
    mocker.patch.object(glta, "DEFAULT_UF_ADDRESS", "mock_uf_address")
    mocker.patch.object(glta, "DEFAULT_COUNTER_VAL", "JPY")
    mocker.patch.object(glta, "symbol", "¥")

    # main関数の実行
    await glta.main()

    # 出力の確認
    captured = capsys.readouterr()
    assert "Failed to get staking info." in captured.out


@pytest.mark.asyncio
async def test_main_http_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数が HTTP エラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    # モックの設定（HTTPStatusError が発生する場合）
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

    # main関数の実行
    await glta.main()

    # 出力の確認
    captured = capsys.readouterr()
    assert "HTTP error occurred: 404 - Not Found" in captured.out


@pytest.mark.asyncio
async def test_main_network_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数がネットワークエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    # モックの設定（RequestError が発生する場合）
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block",
        side_effect=httpx.RequestError("Network Error"),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    # main関数の実行
    await glta.main()

    # 出力の確認
    captured = capsys.readouterr()
    assert "Network error occurred: Network Error" in captured.out


@pytest.mark.asyncio
async def test_main_unexpected_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数が予期しないエラーを適切に処理することをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    # モックの設定（予期しないエラーが発生する場合）
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.get_latest_block",
        side_effect=Exception("Unexpected Error"),
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation.TracingClient"
    )

    # main関数の実行
    await glta.main()

    # 出力の確認
    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_tracing_client(mocker: MockerFixture) -> None:
    """
    TracingClient クラスが正しく動作することをテストする

    :param mocker: pytestのモッカー
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


@pytest.mark.asyncio
async def test_log_request(capsys: pytest.CaptureFixture[str]) -> None:
    """
    log_request 関数が正しくリクエストをログに記録することをテストする

    :param capsys: 標準出力をキャプチャするフィクスチャ
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
    log_response 関数が正しくレスポンスをログに記録することをテストする

    :param capsys: 標準出力をキャプチャするフィクスチャ
    :param mocker: pytestのモッカー
    """
    mock_request = httpx.Request("GET", "https://example.com")
    mock_response = mocker.AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.request = mock_request
    await glta.log_response(mock_response)
    captured = capsys.readouterr()
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
