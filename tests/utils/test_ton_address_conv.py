from typing import Any, Dict

import pytest
from pytest_mock import MockerFixture
from pytoniq_core.boc.address import AddressError

from ton_txns_data_conv.utils import ton_address_conv


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """
    モックの設定を提供するフィクスチャ

    :return: モックの設定辞書
    """
    return {
        "ton_info": {
            "user_friendly_address": "EQCBmcW4SvO1FqNrDKdO-h1s24KN6PtQbmBCF_JaRVkKyA5l"
        }
    }


@pytest.fixture
def mock_address(mocker: MockerFixture) -> Any:
    """
    モックのAddressオブジェクトを提供するフィクスチャ

    :param mocker: pytestのモッカー
    :return: モックのAddressオブジェクト
    """
    mock = mocker.Mock()
    mock.to_str.return_value = "EQDOIc2NfCox4MbFtPf7WTZ-0PyYmlZO8EQzf5poIehsgTlm"
    return mock


def test_load_config_success(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    mock_address: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    設定ファイルから正しくアドレスを読み込み、変換できることをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックの設定
    :param mock_address: モックのAddressオブジェクト
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        return_value=mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.Address", return_value=mock_address
    )

    ton_address_conv.main()

    captured = capsys.readouterr()
    assert (
        "User-friendly, Bounceable, URL-safe, Not test-only: EQDOIc2NfCox4MbFtPf7WTZ-0PyYmlZO8EQzf5poIehsgTlm"
        in captured.out
    )


def test_missing_address_config(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    設定ファイルにアドレスが設定されていない場合のエラー処理をテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config", return_value={}
    )

    with pytest.raises(SystemExit):
        ton_address_conv.main()

    captured = capsys.readouterr()
    assert (
        "Error: Please set 'user_friendly_address' in the config.toml file."
        in captured.out
    )


def test_invalid_address(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    無効なアドレスが設定されている場合のエラー処理をテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックの設定
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        return_value=mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.Address",
        side_effect=AddressError("Invalid address"),
    )

    with pytest.raises(SystemExit):
        ton_address_conv.main()

    captured = capsys.readouterr()
    assert "Error: Invalid user_friendly_address. Invalid address" in captured.out


def test_get_address_variations(mock_address: Any) -> None:
    """
    get_address_variations 関数をテストする

    :param mock_address: モックのAddressオブジェクト
    """
    variations = ton_address_conv.get_address_variations(mock_address)
    assert len(variations) == 5
    assert all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in variations.items()
    )

    # 各バリエーションのパラメータをテスト
    expected_calls = [
        {
            "is_user_friendly": True,
            "is_bounceable": True,
            "is_url_safe": True,
            "is_test_only": False,
        },
        {
            "is_user_friendly": True,
            "is_bounceable": True,
            "is_url_safe": False,
            "is_test_only": False,
        },
        {
            "is_user_friendly": True,
            "is_bounceable": False,
            "is_url_safe": True,
            "is_test_only": False,
        },
        {
            "is_user_friendly": True,
            "is_bounceable": True,
            "is_url_safe": True,
            "is_test_only": True,
        },
        {
            "is_user_friendly": True,
            "is_bounceable": False,
            "is_url_safe": True,
            "is_test_only": True,
        },
    ]
    for call in expected_calls:
        mock_address.to_str.assert_any_call(**call)


def test_main_function_error_handling(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数のエラーハンドリングをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        side_effect=Exception("Config loading error"),
    )

    with pytest.raises(Exception) as excinfo:
        ton_address_conv.main()

    assert str(excinfo.value) == "Config loading error"
    captured = capsys.readouterr()
    assert captured.out == ""  # 標準出力には何も出力されないはず


def test_main_function_unexpected_error(
    mocker: MockerFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    main 関数内での予期しないエラーのハンドリングをテストする

    :param mocker: pytestのモッカー
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        return_value={"ton_info": {"user_friendly_address": "valid_address"}},
    )
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.Address",
        side_effect=Exception("Unexpected error"),
    )

    with pytest.raises(SystemExit) as excinfo:
        ton_address_conv.main()

    assert excinfo.value.code == 1
    captured = capsys.readouterr()
    assert (
        "Error: An unexpected error occurred while processing the address. Unexpected error"
        in captured.out
    )


def test_address_conversion_error(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    mock_address: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    アドレス変換中にエラーが発生した場合のエラー処理をテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックの設定
    :param mock_address: モックのAddressオブジェクト
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        return_value=mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.Address", return_value=mock_address
    )
    mock_address.to_str.side_effect = AddressError("Conversion error")

    with pytest.raises(SystemExit):
        ton_address_conv.main()

    captured = capsys.readouterr()
    assert "Error: Invalid user_friendly_address. Conversion error" in captured.out


def test_main_function_complete_flow(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    mock_address: Any,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    main 関数の完全なフローをテストする

    :param mocker: pytestのモッカー
    :param mock_config: モックの設定
    :param mock_address: モックのAddressオブジェクト
    :param capsys: 標準出力をキャプチャするフィクスチャ
    """
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.load_config",
        return_value=mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.utils.ton_address_conv.Address", return_value=mock_address
    )

    ton_address_conv.main()

    captured = capsys.readouterr()
    assert all(
        description in captured.out
        for description in [
            "User-friendly, Bounceable, URL-safe, Not test-only",
            "User-friendly, Bounceable, Not URL-safe, Not test-only",
            "User-friendly, Not Bounceable, URL-safe, Not test-only",
            "User-friendly, Bounceable, URL-safe, Test-only",
            "User-friendly, Not Bounceable, URL-safe, Test-only",
        ]
    )
