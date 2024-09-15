import importlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest
from freezegun import freeze_time
from pytest_mock import MockerFixture
from requests.exceptions import RequestException

import ton_txns_data_conv.account.get_latest_ton_amount_calculation_sync as gltacs


@pytest.fixture
def mock_session(mocker: MockerFixture) -> Any:
    """
    Mock session fixture.

    :param mocker: pytest mocker fixture
    :return: mocked session object
    """
    return mocker.Mock()


@pytest.fixture
def mock_config(mocker: MockerFixture) -> Dict[str, Any]:
    """
    Mock configuration fixture.

    :param mocker: pytest mocker fixture
    :return: mocked configuration dictionary
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
def mock_load_config(mocker: MockerFixture, mock_config: Dict[str, Any]) -> None:
    """
    Automatically mock the load_config function.

    :param mocker: pytest mocker fixture
    :param mock_config: mock configuration dictionary
    """
    mocker.patch.object(gltacs, "load_config", return_value=mock_config)


def test_initialize_address_success(
    mock_config: Dict[str, Any], mocker: MockerFixture
) -> None:
    """
    Test initialize_address function for successful execution.

    :param mock_config: mock configuration dictionary
    :param mocker: pytest mocker fixture
    """
    mocker.patch.object(gltacs, "config", mock_config)
    mocker.patch.object(gltacs, "Address")  # モックAddressオブジェクトを作成

    gltacs.initialize_address()

    assert gltacs.DEFAULT_UF_ADDRESS == mock_config["ton_info"]["user_friendly_address"]
    gltacs.Address.assert_called_once_with(
        mock_config["ton_info"]["user_friendly_address"]
    )


def test_initialize_address_failure(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    Test initialize_address function for failure case.

    :param mocker: pytest mocker fixture
    :param mock_config: mock configuration dictionary
    """
    invalid_config = mock_config.copy()
    invalid_config["ton_info"]["user_friendly_address"] = ""
    mocker.patch.object(gltacs, "config", invalid_config)

    with pytest.raises(SystemExit) as excinfo:
        gltacs.initialize_address()
    assert excinfo.value.code == 1


def test_create_session() -> None:
    """Test the create_session function."""
    session = gltacs.create_session()
    assert session is not None
    assert session.adapters["http://"].max_retries.total == 3
    assert session.adapters["https://"].max_retries.total == 3


@pytest.mark.parametrize("enable_tracing", [True, False])
def test_make_request(
    mocker: MockerFixture,
    mock_session: Any,
    enable_tracing: bool,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Test the make_request function with both tracing enabled and disabled.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param enable_tracing: boolean flag for enabling tracing
    :param capsys: pytest fixture to capture stdout and stderr
    """
    mocker.patch.object(gltacs, "ENABLE_TRACING", enable_tracing)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.url = "https://example.com"
    mock_session.request.return_value = mock_response

    mocker.patch("time.time", side_effect=[0, 1])  # Start time and end time

    response = gltacs.make_request(mock_session, "GET", "https://example.com")

    assert response == mock_response
    mock_session.request.assert_called_once_with("GET", "https://example.com")

    captured = capsys.readouterr()
    if enable_tracing:
        assert "Sending request: GET https://example.com" in captured.out
        assert "Received response: 200 from https://example.com" in captured.out
        assert "Request took 1.00 seconds" in captured.out
    else:
        assert captured.out == ""


def test_get_latest_block(mocker: MockerFixture, mock_session: Any) -> None:
    """
    Test the get_latest_block function.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"last": {"seqno": 12345}, "now": 1628694000}
    mocker.patch.object(gltacs, "make_request", return_value=mock_response)

    with freeze_time("2021-08-11 15:00:00"):
        seqno, ts_utc, ts_local = gltacs.get_latest_block(mock_session)

    assert seqno == 12345
    assert ts_utc == datetime(2021, 8, 11, 15, 0, tzinfo=timezone.utc)
    expected_local = datetime(2021, 8, 12, 0, 0, tzinfo=gltacs.TZ)
    assert ts_local == expected_local


@pytest.mark.parametrize(
    "result_data, expected_output",
    [
        (
            [
                {"value": "1000000000"},
                {"value": "2000000000"},
                {"value": "3000000000"},
            ],
            None,
        ),
        (
            [
                {"value": "1000000000"},
                {"value": "2000000000"},
                {"value": "3000000000"},
                {"value": "4000000000"},
            ],
            {
                "Seqno": 12345,
                "Timestamp": "2021-08-11 21:00:00",
                "Staked Amount": 1.0,
                "Pending Deposit": 2.0,
                "Pending Withdraw": 3.0,
                "Withdraw Available": 4.0,
                "Total Staked Amount": 10.0,
            },
        ),
        (
            [
                {"value": "1000000000"},
                {"value": "2000000000"},
                {"value": "3000000000"},
                {"value": "4000000000"},
                {"value": "5000000000"},
            ],
            {
                "Seqno": 12345,
                "Timestamp": "2021-08-11 21:00:00",
                "Staked Amount": 1.0,
                "Pending Deposit": 2.0,
                "Pending Withdraw": 3.0,
                "Withdraw Available": 4.0,
                "Total Staked Amount": 10.0,
            },
        ),
        ([], None),
    ],
)
def test_get_staking_info(
    mocker: MockerFixture,
    mock_session: Any,
    result_data: List[Dict[str, str]],
    expected_output: Optional[Dict[str, Any]],
) -> None:
    """
    Test the get_staking_info function with various input data.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param result_data: input data for the test
    :param expected_output: expected output of the function
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"result": result_data}
    mocker.patch.object(gltacs, "make_request", return_value=mock_response)

    timestamp = datetime(2021, 8, 11, 12, 0, tzinfo=timezone.utc)
    result = gltacs.get_staking_info(
        mock_session, 12345, timestamp, "pool_address", "member_address"
    )

    assert result == expected_output


def test_ton_rate_by_ticker(mocker: MockerFixture, mock_session: Any) -> None:
    """
    Test the ton_rate_by_ticker function.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"rates": {"TON": {"prices": {"JPY": "200.0"}}}}
    mocker.patch.object(gltacs, "make_request", return_value=mock_response)

    rate = gltacs.ton_rate_by_ticker(mock_session)

    assert rate == 200.0


def test_get_ton_balance(mocker: MockerFixture, mock_session: Any) -> None:
    """
    Test the get_ton_balance function.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"balance": "5000000000"}
    mocker.patch.object(gltacs, "make_request", return_value=mock_response)

    balance = gltacs.get_ton_balance(mock_session, "user_friendly_address")

    assert balance == 5.0


def test_get_currency_symbol_exception_handling(mocker: MockerFixture) -> None:
    """
    get_currency_symbolが例外を発生させた場合のテスト
    """
    # モジュールレベルの変数をパッチ
    mocker.patch.object(gltacs, "DEFAULT_COUNTER_VAL", "INVALID")

    # get_currency_symbolをモックして例外を発生させる
    mock_get_currency_symbol = mocker.patch("babel.numbers.get_currency_symbol")
    mock_get_currency_symbol.side_effect = ValueError()

    # モジュールを再読み込みして、パッチされた値を反映
    importlib.reload(gltacs)

    # symbolの値を確認
    assert gltacs.symbol == "¥"

    # TypeErrorの場合もテスト
    mock_get_currency_symbol.side_effect = TypeError()
    importlib.reload(gltacs)
    assert gltacs.symbol == "¥"


def test_main_success(
    mocker: MockerFixture, mock_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Test the main function for successful execution.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param capsys: pytest fixture to capture stdout and stderr
    """
    mocker.patch.object(gltacs, "initialize_address")
    mocker.patch.object(gltacs, "create_session", return_value=mock_session)
    mocker.patch.object(
        gltacs,
        "get_latest_block",
        return_value=(
            12345,
            datetime(2021, 8, 11, 12, 0, tzinfo=timezone.utc),
            datetime(2021, 8, 11, 21, 0, tzinfo=gltacs.TZ),
        ),
    )
    mocker.patch.object(gltacs, "get_ton_balance", return_value=10.0)
    mocker.patch.object(
        gltacs,
        "get_staking_info",
        return_value={
            "Timestamp": "2021-08-11 21:00:00",
            "Total Staked Amount": 20.0,
        },
    )
    mocker.patch.object(gltacs, "ton_rate_by_ticker", return_value=200.0)

    gltacs.main()

    captured = capsys.readouterr()
    assert (
        "seqno: 12345 / utc:2021-08-11 12:00:00+00:00 / local:2021-08-11 21:00:00+09:00"
        in captured.out
    )
    assert "Total Staked Amount: 20.000000000" in captured.out
    assert "Balance: 10.000000000" in captured.out
    assert "Hold TON: 30.000000000" in captured.out
    assert "Rate: 200.00" in captured.out


def test_main_no_staking_info(
    mocker: MockerFixture, mock_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Test the main function when no staking info is available.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param capsys: pytest fixture to capture stdout and stderr
    """
    mocker.patch.object(gltacs, "initialize_address")
    mocker.patch.object(gltacs, "create_session", return_value=mock_session)
    mocker.patch.object(
        gltacs,
        "get_latest_block",
        return_value=(
            12345,
            datetime(2021, 8, 11, 12, 0, tzinfo=timezone.utc),
            datetime(2021, 8, 11, 21, 0, tzinfo=gltacs.TZ),
        ),
    )
    mocker.patch.object(gltacs, "get_ton_balance", return_value=10.0)
    mocker.patch.object(gltacs, "get_staking_info", return_value=None)

    gltacs.main()

    captured = capsys.readouterr()
    assert "Failed to get staking info." in captured.out


@pytest.mark.parametrize("exception", [RequestException("Test error")])
def test_main_exception(
    mocker: MockerFixture,
    mock_session: Any,
    exception: Exception,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Test the main function when an exception occurs.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param exception: exception to be raised
    :param capsys: pytest fixture to capture stdout and stderr
    """
    mocker.patch.object(gltacs, "initialize_address")
    mocker.patch.object(gltacs, "create_session", return_value=mock_session)
    mocker.patch.object(gltacs, "get_latest_block", side_effect=exception)

    gltacs.main()

    captured = capsys.readouterr()
    assert "An error occurred: Test error" in captured.out


def test_log_request(capsys: pytest.CaptureFixture[str], mocker: MockerFixture) -> None:
    """
    Test the log_request function.

    :param capsys: pytest fixture to capture stdout and stderr
    :param mocker: pytest mocker fixture
    """
    mocker.patch.object(gltacs, "ENABLE_TRACING", True)
    gltacs.log_request("GET", "https://example.com")
    captured = capsys.readouterr()
    assert "Sending request: GET https://example.com" in captured.out

    mocker.patch.object(gltacs, "ENABLE_TRACING", False)
    gltacs.log_request("GET", "https://example.com")
    captured = capsys.readouterr()
    assert captured.out == ""


def test_log_response(
    capsys: pytest.CaptureFixture[str], mocker: MockerFixture
) -> None:
    """
    Test the log_response function.

    :param capsys: pytest fixture to capture stdout and stderr
    :param mocker: pytest mocker fixture
    """
    mocker.patch.object(gltacs, "ENABLE_TRACING", True)
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.url = "https://example.com"
    gltacs.log_response(mock_response)
    captured = capsys.readouterr()
    assert "Received response: 200 from https://example.com" in captured.out

    mocker.patch.object(gltacs, "ENABLE_TRACING", False)
    gltacs.log_response(mock_response)
    captured = capsys.readouterr()
    assert captured.out == ""


def test_make_request_raise_for_status(
    mocker: MockerFixture, mock_session: Any
) -> None:
    """
    Test the make_request function when raise_for_status is called.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    """
    mock_response = mocker.Mock()
    mock_response.raise_for_status.side_effect = RequestException("Test error")
    mock_session.request.return_value = mock_response

    with pytest.raises(RequestException, match="Test error"):
        gltacs.make_request(mock_session, "GET", "https://example.com")


def test_ton_rate_by_ticker_custom_ticker(
    mocker: MockerFixture, mock_session: Any
) -> None:
    """
    Test the ton_rate_by_ticker function with a custom ticker.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"rates": {"TON": {"prices": {"USD": "1.5"}}}}
    mocker.patch.object(gltacs, "make_request", return_value=mock_response)

    rate = gltacs.ton_rate_by_ticker(mock_session, "usd")

    assert rate == 1.5


def test_main_initialize_address_failure(
    mocker: MockerFixture, mock_session: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Test the main function when initialize_address fails.

    :param mocker: pytest mocker fixture
    :param mock_session: mocked session object
    :param capsys: pytest fixture to capture stdout and stderr
    """
    mocker.patch.object(gltacs, "initialize_address", side_effect=SystemExit(1))
    mocker.patch.object(gltacs, "create_session", return_value=mock_session)

    with pytest.raises(SystemExit) as excinfo:
        gltacs.main()

    assert excinfo.value.code == 1
