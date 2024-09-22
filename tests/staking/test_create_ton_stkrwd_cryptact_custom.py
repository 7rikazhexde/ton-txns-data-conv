import datetime
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest
import pytz
from freezegun import freeze_time
from pytest_mock import MockerFixture

from ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom import (
    create_cryptact_custom_csv,
    create_cryptact_custom_data,
    main,
)


@pytest.fixture
def sample_transaction() -> Dict[str, Any]:
    """
    サンプルのトランザクションデータを提供するフィクスチャ。

    :return: サンプルのトランザクションデータ
    """
    return {"hash": "test_hash", "now": 1628097600, "in_msg": {"value": "1000000000"}}


@pytest.fixture
def sample_transactions() -> List[Dict[str, Any]]:
    """
    サンプルのトランザクションリストを提供するフィクスチャ。

    :return: サンプルのトランザクションリスト
    """
    return [
        {"hash": "test_hash_1", "now": 1628097600, "in_msg": {"value": "1000000000"}},
        {"hash": "test_hash_2", "now": 1628184000, "in_msg": {"value": "2000000000"}},
    ]


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """
    モックの設定を提供するフィクスチャ。

    :return: モックの設定辞書
    """
    return {
        "ton_info": {
            "user_friendly_address": "test_address",
            "transaction_history_period": 30,
        },
        "file_save_option": {"save_allow_json": True, "save_allow_csv": True},
    }


# def test_create_cryptact_custom_data(sample_transaction: Dict[str, Any]) -> None:
#    """
#    create_cryptact_custom_data 関数のテスト。
#
#    :param sample_transaction: サンプルのトランザクションデータ
#    """
#    result = create_cryptact_custom_data(sample_transaction)
#    assert result is not None
#    assert result[0] == "'2021/08/05 02:20:00"
#    assert result[1] == "STAKING"
#    assert result[4] == "1.000000000"


# def test_create_cryptact_custom_data_invalid() -> None:
#    """
#    create_cryptact_custom_data 関数の無効なデータに対するテスト。
#    """
#    invalid_transaction = {"in_msg": {"value": "0"}}
#    assert create_cryptact_custom_data(invalid_transaction) is None


# def test_create_cryptact_custom_data(sample_transaction: Dict[str, Any]) -> None:
#    """
#    create_cryptact_custom_data 関数のテスト。
#
#    :param sample_transaction: サンプルのトランザクションデータ
#    """
#    print(
#        f"\nCurrent timezone: {datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo}"
#    )
#    print(f"Sample transaction: {sample_transaction}")
#
#    result = create_cryptact_custom_data(sample_transaction)
#    assert result is not None, "Result should not be None"
#
#    print(f"Result: {result}")
#
#    expected_time = datetime.datetime.fromtimestamp(
#        sample_transaction["now"], pytz.UTC
#    ).astimezone(pytz.timezone("Asia/Tokyo"))
#    expected_str = f"'{expected_time.strftime('%Y/%m/%d %H:%M:%S')}"
#    print(f"Expected time: {expected_str}")
#
#    assert result[0] == expected_str, f"Expected {expected_str}, but got {result[0]}"
#    assert result[1] == "STAKING", f"Expected 'STAKING', but got {result[1]}"
#    assert result[4] == "1.000000000", f"Expected '1.000000000', but got {result[4]}"
#
#    # UTCでのテスト
#    result_utc = create_cryptact_custom_data(
#        sample_transaction, transaction_timezone="UTC"
#    )
#    print(f"UTC Result: {result_utc}")
#    expected_utc_str = f"'{datetime.datetime.fromtimestamp(sample_transaction['now'], pytz.UTC).strftime('%Y/%m/%d %H:%M:%S')}"
#    assert (
#        result_utc[0] == expected_utc_str
#    ), f"Expected {expected_utc_str}, but got {result_utc[0]}"
#
#
# def test_create_cryptact_custom_data_invalid(
#    sample_transaction: Dict[str, Any],
# ) -> None:
#    """
#    create_cryptact_custom_data 関数の無効なデータに対するテスト。
#
#    :param sample_transaction: サンプルのトランザクションデータ
#    """
#    # 無効な取引額（0）のテスト
#    invalid_transaction = sample_transaction.copy()
#    invalid_transaction["in_msg"]["value"] = "0"
#    assert create_cryptact_custom_data(invalid_transaction) is None
#
#    # in_msgが存在しない場合のテスト
#    invalid_transaction = sample_transaction.copy()
#    del invalid_transaction["in_msg"]
#    assert create_cryptact_custom_data(invalid_transaction) is None
#
#    # nowフィールドが存在しない場合のテスト
#    invalid_transaction = sample_transaction.copy()
#    del invalid_transaction["now"]
#    assert create_cryptact_custom_data(invalid_transaction) is None


def test_create_cryptact_custom_data(sample_transaction: Dict[str, Any]) -> None:
    """
    create_cryptact_custom_data 関数のテスト。

    :param sample_transaction: サンプルのトランザクションデータ
    """
    print(
        f"\nCurrent timezone: {datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo}"
    )
    print(f"Sample transaction: {sample_transaction}")

    result = create_cryptact_custom_data(sample_transaction)
    assert result is not None, "Result should not be None"

    print(f"Result: {result}")

    expected_time = datetime.datetime.fromtimestamp(
        sample_transaction["now"], pytz.UTC
    ).astimezone(pytz.timezone("Asia/Tokyo"))
    expected_str = f"'{expected_time.strftime('%Y/%m/%d %H:%M:%S')}"
    print(f"Expected time: {expected_str}")

    assert result[0] == expected_str, f"Expected {expected_str}, but got {result[0]}"
    assert result[1] == "STAKING", f"Expected 'STAKING', but got {result[1]}"
    assert result[4] == "1.000000000", f"Expected '1.000000000', but got {result[4]}"

    # UTCでのテスト
    result_utc = create_cryptact_custom_data(
        sample_transaction, transaction_timezone="UTC"
    )
    assert result_utc is not None, "UTC result should not be None"

    print(f"UTC Result: {result_utc}")
    expected_utc_str = f"'{datetime.datetime.fromtimestamp(sample_transaction['now'], pytz.UTC).strftime('%Y/%m/%d %H:%M:%S')}"
    assert (
        result_utc[0] == expected_utc_str
    ), f"Expected {expected_utc_str}, but got {result_utc[0]}"


def test_create_cryptact_custom_data_invalid(
    sample_transaction: Dict[str, Any],
) -> None:
    # 無効な取引額（0）のテスト
    invalid_transaction = sample_transaction.copy()
    invalid_transaction["in_msg"]["value"] = "0"
    assert create_cryptact_custom_data(invalid_transaction) is None

    # in_msgが存在しない場合のテスト
    invalid_transaction = sample_transaction.copy()
    del invalid_transaction["in_msg"]
    assert create_cryptact_custom_data(invalid_transaction) is None

    # nowフィールドが存在しない場合のテスト
    invalid_transaction = sample_transaction.copy()
    del invalid_transaction["now"]
    assert create_cryptact_custom_data(invalid_transaction) is None


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    create_cryptact_custom_csv 関数の基本的な動作のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch("builtins.input", return_value="y")
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    create_cryptact_custom_csv(sample_transactions)

    csv_files = list(output_dir.glob("*.csv"))
    assert len(csv_files) == 1

    df = pd.read_csv(csv_files[0])
    assert len(df) == 2
    assert df.columns.tolist() == [
        "Timestamp",
        "Action",
        "Source",
        "Base",
        "Volume",
        "Price",
        "Counter",
        "Fee",
        "FeeCcy",
        "Comment",
    ]


def test_create_cryptact_custom_csv_no_transactions(mocker: MockerFixture) -> None:
    """
    トランザクションがない場合の create_cryptact_custom_csv 関数のテスト。

    :param mocker: pytest mocker fixture
    """
    mock_print = mocker.patch("builtins.print")
    create_cryptact_custom_csv([])
    mock_print.assert_called_once_with(
        "No valid transactions found. CSV file not created."
    )


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv_with_filename(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    カスタムファイル名を使用した create_cryptact_custom_csv 関数のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    filename = "custom_filename"
    create_cryptact_custom_csv(sample_transactions, filename=filename)

    expected_file = output_dir / f"transactions_{filename}_N=2_2024-08-14.csv"
    assert expected_file.exists()


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv_default_filename(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    デフォルトのファイル名を使用した create_cryptact_custom_csv 関数のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    create_cryptact_custom_csv(sample_transactions)  # デフォルトのfilenameを使用

    expected_file = output_dir / "transactions_tonindex_v3_N=2_2024-08-14.csv"
    assert expected_file.exists()


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv_empty_filename(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    空のファイル名を使用した create_cryptact_custom_csv 関数のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    create_cryptact_custom_csv(sample_transactions, filename="")

    expected_file = output_dir / "transactions_N=2_2024-08-14.csv"
    assert expected_file.exists()


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv_file_exists_overwrite(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    既存ファイルを上書きする場合の create_cryptact_custom_csv 関数のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch("builtins.input", return_value="y")  # ユーザーが上書きを承認
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    existing_file = output_dir / "transactions_tonindex_v3_N=2_2024-08-14.csv"
    existing_file.write_text("existing content")

    mock_print = mocker.patch("builtins.print")
    create_cryptact_custom_csv(sample_transactions)

    assert existing_file.exists()
    assert existing_file.read_text() != "existing content"
    mock_print.assert_any_call(f"CSV file saved: {existing_file}")


@freeze_time("2024-08-14")
def test_create_cryptact_custom_csv_file_exists_no_overwrite(
    sample_transactions: List[Dict[str, Any]], mocker: MockerFixture, tmp_path: Path
) -> None:
    """
    既存ファイルを上書きしない場合の create_cryptact_custom_csv 関数のテスト。

    :param sample_transactions: サンプルのトランザクションリスト
    :param mocker: pytest mocker fixture
    :param tmp_path: 一時ディレクトリのパス
    """
    mocker.patch("builtins.input", return_value="n")  # ユーザーが上書きを拒否
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.project_root",
        tmp_path,
    )

    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    existing_file = output_dir / "transactions_tonindex_v3_N=2_2024-08-14.csv"
    existing_file.write_text("existing content")

    mock_print = mocker.patch("builtins.print")
    create_cryptact_custom_csv(sample_transactions)

    assert existing_file.exists()
    assert existing_file.read_text() == "existing content"
    mock_print.assert_called_with("File not saved.")


# def test_main(
#    mocker: MockerFixture,
#    mock_config: Dict[str, Any],
#    sample_transactions: List[Dict[str, Any]],
# ) -> None:
#    """
#    main 関数のテスト。
#
#    :param mocker: pytest mocker fixture
#    :param mock_config: モックの設定
#    :param sample_transactions: サンプルのトランザクションリスト
#    """
#    mocker.patch(
#        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.load_config",
#        return_value=mock_config,
#    )
#    mocker.patch(
#        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.get_transactions_v3",
#        return_value=sample_transactions,
#    )
#    mock_create_csv = mocker.patch(
#        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.create_cryptact_custom_csv"
#    )
#    mock_print = mocker.patch("builtins.print")
#
#    main()
#
#    mock_create_csv.assert_called_once_with(sample_transactions)
#    mock_print.assert_called_once_with("TON Index API v3: Processed 2 transactions")


def test_main(mocker: MockerFixture) -> None:
    # モックの設定
    mock_config = {
        "ton_info": {
            "user_friendly_address": "test_address",
            "transaction_history_period": 30,
            "timezone": "Asia/Tokyo",
        },
        "file_save_option": {"save_allow_json": True, "save_allow_csv": True},
    }
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.load_config",
        return_value=mock_config,
    )

    mock_get_transactions = mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.get_transactions_v3"
    )
    mock_create_csv = mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.create_cryptact_custom_csv"
    )

    # main関数の実行
    main()

    # アサーション
    mock_get_transactions.assert_called_once()
    mock_create_csv.assert_called_once()


def test_main_save_csv_false(
    mocker: MockerFixture, mock_config: Dict[str, Any]
) -> None:
    """
    CSVを保存しない設定の場合の main 関数のテスト。

    :param mocker: pytest mocker fixture
    :param mock_config: モックの設定
    """
    mock_config["file_save_option"]["save_allow_csv"] = False
    mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.load_config",
        return_value=mock_config,
    )
    mock_get_transactions = mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.get_transactions_v3"
    )
    mock_create_csv = mocker.patch(
        "ton_txns_data_conv.staking.create_ton_stkrwd_cryptact_custom.create_cryptact_custom_csv"
    )

    main()

    mock_get_transactions.assert_not_called()
    mock_create_csv.assert_not_called()
