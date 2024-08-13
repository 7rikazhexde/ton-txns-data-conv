import asyncio
import gzip
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from aiohttp import ClientError, ClientResponseError, ClientSession, TraceConfig
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import (
    get_latest_ton_amount_calculation_async_aiohttp as glta,
)


@pytest.fixture
def mock_aiohttp_session(mocker: MockerFixture) -> MockerFixture:
    """
    aiohttp.ClientSession のモックを提供するフィクスチャ

    このフィクスチャは、aiohttp.ClientSession のモックを作成し、
    テスト中に使用できるようにします。これにより、実際のネットワーク
    リクエストを行わずにテストを実行することができます。

    :param mocker: pytestのモッカー
    :return: モックされた ClientSession
    """
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mocker.patch("aiohttp.ClientSession", return_value=mock_session)
    return mock_session


@pytest.mark.asyncio
async def test_fetch_data_http_error(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が HTTP エラーを適切に処理することをテストする

    HTTPエラーが発生した場合、ClientResponseErrorが適切に発生し、
    正しいステータスコードとメッセージが含まれていることを確認する。

    :param mocker: pytestのモッカー
    """
    # モックレスポンスの設定
    mock_response = mocker.AsyncMock()
    mock_response.status = 404
    mock_response.reason = "Not Found"
    mock_response.headers = {
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
    }
    mock_response.read = mocker.AsyncMock(return_value=b'{"error": "Not Found"}')

    # request_infoとhistoryのモックを作成
    mock_request_info = mocker.Mock()
    mock_history = mocker.Mock()
    mock_response.request_info = mock_request_info
    mock_response.history = mock_history

    # セッションのgetメソッドが非同期コンテキストマネージャを返すように設定
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    # ClientResponseErrorが発生することを確認
    with pytest.raises(ClientResponseError) as exc_info:
        await glta.fetch_data(mock_session, "https://example.com")

    # 発生した例外の詳細を確認
    assert exc_info.value.status == 404
    assert "Not Found" in str(exc_info.value)

    # モックメソッドが正しく呼び出されたことを確認
    mock_session.get.assert_called_once_with("https://example.com")
    # raise_for_status()の呼び出しチェックを削除


@pytest.mark.asyncio
async def test_fetch_data_gzip_success(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が gzip 圧縮されたデータを正常に解凍できることをテストする

    gzip圧縮されたJSONデータが正しく解凍され、期待通りの結果が返されることを確認する。

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

    圧縮されていないデータでもエラーが発生せずに、正しいJSONデータが返されることを確認する。

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Encoding": "gzip"}
    mock_response.read = mocker.AsyncMock(
        return_value=b'{"key": "value"}'
    )  # Not gzipped

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    result = await glta.fetch_data(mock_session, "https://example.com")
    assert result == {"key": "value"}


@pytest.mark.asyncio
async def test_fetch_data_non_gzip(mocker: MockerFixture) -> None:
    """
    fetch_data 関数が非 gzip 圧縮データを正しく処理することをテストする

    通常のJSONデータが正しく処理され、期待通りの結果が返されることを確認する。

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

    JSONオブジェクトではなくリスト形式のデータが渡された場合、
    適切なValueErrorが発生することを確認する。

    :param mocker: pytestのモッカー
    """
    mock_response = mocker.AsyncMock()
    mock_response.status = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.read = mocker.AsyncMock(
        return_value=b'["This", "is", "a", "list"]'
    )  # リストを返すJSON

    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_session.get.return_value.__aenter__.return_value = mock_response

    with pytest.raises(ValueError, match="Expected a JSON object, got list"):
        await glta.fetch_data(mock_session, "https://example.com")

    mock_session.get.assert_called_once_with("https://example.com")


@pytest.mark.asyncio
async def test_main_client_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数が ClientError を適切に処理することをテストする

    ClientErrorが発生した場合、適切なエラーメッセージが出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=ClientError("Network Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "Network error occurred: Network Error" in captured.out


@pytest.mark.asyncio
async def test_get_latest_block(
    mock_aiohttp_session: MockerFixture, mocker: MockerFixture
) -> None:
    """
    get_latest_block 関数が正しく動作することをテストする

    最新のブロック情報が正しく取得され、期待通りの形式で返されることを確認する。

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

    ステーキング情報が正しく取得され、期待通りの形式で返されることを確認する。

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

    データが不足している場合、Noneが返されることを確認する。

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

    TONのレートが正しく取得され、期待通りの値が返されることを確認する。

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

    TONの残高が正しく取得され、期待通りの値が返されることを確認する。

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

    リクエスト開始時に適切なメッセージがログに出力されることを確認する。

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

    リクエスト終了時に適切なメッセージがログに出力されることを確認する。

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


@pytest.mark.asyncio
async def test_create_trace_config() -> None:
    """
    create_trace_config 関数が正しく動作することをテストする

    トレース設定が正しく作成され、期待通りの設定が含まれていることを確認する。
    """
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
    """
    main 関数が正常に動作することをテストする

    全ての処理が正常に実行され、期待通りの結果が出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
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
    """
    main 関数がステーキング情報なしの場合に適切に処理することをテストする

    ステーキング情報が取得できない場合でも、他の処理が正常に実行され、
    適切なメッセージが出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
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
    """
    main 関数が HTTP エラーを適切に処理することをテストする

    HTTPエラーが発生した場合、適切なエラーメッセージが出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
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
    """
    main 関数がネットワークエラーを適切に処理することをテストする

    ネットワークエラーが発生した場合、適切なエラーメッセージが出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
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
    """
    main 関数がタイムアウトエラーを適切に処理することをテストする

    get_latest_block 関数がタイムアウトエラーを発生させた場合、
    main 関数が適切にエラーをキャッチし、正しいエラーメッセージを
    出力することを確認します。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
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
    """
    main 関数が予期しないエラーを適切に処理することをテストする

    予期しないエラーが発生した場合、適切なエラーメッセージが出力されることを確認する。

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.get_latest_block",
        side_effect=Exception("Unexpected Error"),
    )

    await glta.main()

    captured = capsys.readouterr()
    assert "An unexpected error occurred: Unexpected Error" in captured.out


@pytest.mark.asyncio
async def test_main_with_trace_config(mocker: MockerFixture) -> None:
    """
    main 関数がトレース設定を正しく使用することをテストする

    トレース設定が有効な場合、適切にトレース設定が作成され、
    ClientSessionに正しく適用されることを確認する。
    また、トレース設定が無効な場合の動作も確認する。

    :param mocker: pytestのモッカー
    """
    # ENABLE_TRACINGをTrueに設定
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        True,
    )

    # create_trace_configの実際の実装を使用
    real_create_trace_config = glta.create_trace_config

    # ClientSessionの作成をモック
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_client_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session
    )

    # fetch_dataの戻り値をモック
    mock_fetch_data = mocker.AsyncMock(
        return_value={
            "last": {"seqno": 12345},
            "now": 1628097600,
        }
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.fetch_data",
        mock_fetch_data,
    )

    # その他の必要な関数をモック
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

    # mainを実行
    await glta.main()

    # ClientSessionが正しい引数で呼び出されたことを確認
    _, kwargs = mock_client_session.call_args
    assert "connector" in kwargs
    assert "timeout" in kwargs
    assert "auto_decompress" in kwargs
    assert "trace_configs" in kwargs

    # trace_configsが正しく設定されていることを確認
    trace_configs = kwargs["trace_configs"]
    assert len(trace_configs) == 1
    assert isinstance(trace_configs[0], TraceConfig)
    assert len(trace_configs[0].on_request_start) == 1
    assert len(trace_configs[0].on_request_end) == 1

    # 実際にcreate_trace_configが呼び出されたことを確認
    real_trace_config = real_create_trace_config(True)
    assert real_trace_config is not None
    assert trace_configs[0].on_request_start == real_trace_config.on_request_start
    assert trace_configs[0].on_request_end == real_trace_config.on_request_end

    # fetch_dataが呼び出されたことを確認
    mock_fetch_data.assert_called()

    # トレース設定が無効な場合のテスト
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        False,
    )

    # ClientSessionの呼び出しをリセット
    mock_client_session.reset_mock()

    # mainを再度実行
    await glta.main()

    # トレース設定が無効の場合、trace_configsが含まれていないことを確認
    _, kwargs = mock_client_session.call_args
    assert "trace_configs" not in kwargs


@pytest.mark.asyncio
async def test_main_trace_config_branch(mocker: MockerFixture) -> None:
    """
    main 関数のトレース設定分岐を正しく処理することをテストする

    トレース設定が有効な場合のみ、トレース設定が作成され適用されることを確認する。

    :param mocker: pytestのモッカー
    """
    # ENABLE_TRACINGをTrueに設定
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        True,
    )

    # create_trace_configのモックを作成
    mock_create_trace_config = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.create_trace_config"
    )

    # TraceConfigのインスタンスを作成
    mock_trace_config = mocker.MagicMock(spec=TraceConfig)
    mock_create_trace_config.return_value = mock_trace_config

    # ClientSessionの作成をモック
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_client_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session
    )

    # その他の関数をモックして、main関数がエラーなく実行されるようにする
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

    # main関数を実行
    await glta.main()

    # ClientSessionが正しい引数で呼び出されたことを確認
    _, kwargs = mock_client_session.call_args
    assert "trace_configs" in kwargs
    trace_configs = kwargs["trace_configs"]
    assert len(trace_configs) == 1
    assert trace_configs[0] is mock_trace_config

    # create_trace_configが正しく呼び出されたことを確認
    mock_create_trace_config.assert_called_once_with(True)


@pytest.mark.asyncio
async def test_main_no_trace_config(mocker: MockerFixture) -> None:
    """
    main 関数がトレース設定なしで正しく動作することをテストする

    トレース設定が無効な場合、トレース設定が作成されずに
    ClientSessionが正しく動作することを確認する。

    :param mocker: pytestのモッカー
    """
    # ENABLE_TRACINGをFalseに設定
    mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.ENABLE_TRACING",
        False,
    )

    # create_trace_configのモックを作成
    mock_create_trace_config = mocker.patch(
        "ton_txns_data_conv.account.get_latest_ton_amount_calculation_async_aiohttp.create_trace_config",
        return_value=None,
    )

    # ClientSessionの作成をモック
    mock_session = mocker.AsyncMock(spec=ClientSession)
    mock_client_session = mocker.patch(
        "aiohttp.ClientSession", return_value=mock_session
    )

    # その他の関数をモックして、main関数がエラーなく実行されるようにする
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

    # main関数を実行
    await glta.main()

    # ClientSessionがtrace_configsを持たないことを確認
    _, kwargs = mock_client_session.call_args
    assert "trace_configs" not in kwargs

    # create_trace_configが正しく呼び出されたことを確認
    mock_create_trace_config.assert_called_once_with(False)
