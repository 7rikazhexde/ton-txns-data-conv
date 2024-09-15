import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import pytest
import requests
from freezegun import freeze_time
from pytest_mock import MockerFixture

from ton_txns_data_conv.account import get_ton_txns_api


@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """
    モックされた設定データを提供するフィクスチャ。

    :return: テスト用の設定データを含む辞書
    """
    return {
        "ton_api_info": {"api_key": "test_api_key"},
        "ton_info": {
            "user_friendly_address": "test_address",
            "transaction_history_period": 30,
        },
        "file_save_option": {"save_allow_json": True},
    }


@pytest.fixture
def mock_transactions() -> List[Dict[str, Any]]:
    """
    モックされたトランザクションデータを提供するフィクスチャ。

    :return: テスト用のトランザクションデータのリスト
    """
    return [
        {"id": 1, "amount": 1000000000},
        {"id": 2, "amount": 2000000000},
    ]


# save_json_file のテスト
def test_save_json_file(
    tmp_path: Path,
    mock_transactions: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    save_json_file関数のテスト。

    JSONファイルが正しく保存されることを確認する。

    :param tmp_path: pytest提供の一時ディレクトリパス
    :param mock_transactions: モックされたトランザクションデータ
    :param monkeypatch: pytestのmonkeypatchフィクスチャ
    """
    monkeypatch.setattr(get_ton_txns_api, "project_root", tmp_path)
    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    filename = "test.json"
    get_ton_txns_api.save_json_file(mock_transactions, filename)

    saved_file = output_dir / filename
    assert saved_file.exists()

    with open(saved_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data == mock_transactions


def test_save_json_file_overwrite_accepted(
    tmp_path: Path,
    mock_transactions: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    save_json_file関数の上書き受け入れテスト。

    既存ファイルの上書きが正しく行われることを確認する。

    :param tmp_path: pytest提供の一時ディレクトリパス
    :param mock_transactions: モックされたトランザクションデータ
    :param monkeypatch: pytestのmonkeypatchフィクスチャ
    """
    monkeypatch.setattr(get_ton_txns_api, "project_root", tmp_path)
    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    filename = "test.json"
    (output_dir / filename).write_text("existing content")

    # Mock user input to always return 'y'
    monkeypatch.setattr("builtins.input", lambda _: "y")

    get_ton_txns_api.save_json_file(mock_transactions, filename)

    saved_file = output_dir / filename
    assert saved_file.exists()

    with open(saved_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data == mock_transactions


def test_save_json_file_overwrite_denied(
    tmp_path: Path,
    mock_transactions: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    save_json_file関数の上書き拒否テスト。

    上書きが拒否された場合の動作を確認する。

    :param tmp_path: pytest提供の一時ディレクトリパス
    :param mock_transactions: モックされたトランザクションデータ
    :param monkeypatch: pytestのmonkeypatchフィクスチャ
    """
    monkeypatch.setattr(get_ton_txns_api, "project_root", tmp_path)
    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    filename = "test.json"
    (output_dir / filename).write_text("existing content")

    monkeypatch.setattr(
        "builtins.input", lambda _: "n"
    )  # Mock user input to deny overwrite

    captured_output = []
    monkeypatch.setattr(
        "builtins.print", lambda *args: captured_output.append(" ".join(map(str, args)))
    )

    get_ton_txns_api.save_json_file(mock_transactions, filename)

    assert "File not saved." in captured_output


def test_save_json_file_overwrite_denied_exit(
    tmp_path: Path,
    mock_transactions: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    save_json_file関数の上書き拒否テスト。

    上書きが拒否された場合の動作を確認する。

    :param tmp_path: pytest提供の一時ディレクトリパス
    :param mock_transactions: モックされたトランザクションデータ
    :param monkeypatch: pytestのmonkeypatchフィクスチャ
    """
    monkeypatch.setattr(get_ton_txns_api, "project_root", tmp_path)
    output_dir = tmp_path / "ton_txns_data_conv" / "output"
    output_dir.mkdir(parents=True)

    filename = "test.json"
    (output_dir / filename).write_text("existing content")

    # Mock user input to always return 'n', causing the function to exit early
    monkeypatch.setattr("builtins.input", lambda _: "n")

    captured_output = []
    monkeypatch.setattr(
        "builtins.print", lambda *args: captured_output.append(" ".join(map(str, args)))
    )

    get_ton_txns_api.save_json_file(mock_transactions, filename)

    assert "File not saved." in captured_output
    saved_file = output_dir / filename
    with open(saved_file, "r") as f:
        saved_data = f.read()
    assert saved_data == "existing content"


# get_transactions_v3 のテスト
@freeze_time("2024-01-01")
@pytest.mark.parametrize("save_json", [True, False])
def test_get_transactions_v3(
    mocker: MockerFixture, mock_transactions: List[Dict[str, Any]], save_json: bool
) -> None:
    """
    get_transactions_v3関数のテスト。

    トランザクションの取得と保存が正しく行われることを確認する。

    :param mocker: pytest-mockのMockerFixture
    :param mock_transactions: モックされたトランザクションデータ
    :param save_json: JSONファイル保存フラグ
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"transactions": mock_transactions}
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.requests.get",
        return_value=mock_response,
    )

    mock_save_json = mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.save_json_file"
    )

    start_time = datetime(2023, 12, 1)
    end_time = datetime(2024, 1, 1)

    result = get_ton_txns_api.get_transactions_v3(
        "test_account", start_time, end_time, save_json=save_json
    )

    assert result == mock_transactions
    if save_json:
        mock_save_json.assert_called_once()
    else:
        mock_save_json.assert_not_called()


def test_get_transactions_v3_multiple_calls(mocker: MockerFixture) -> None:
    """
    get_transactions_v3関数の複数回呼び出しテスト。

    複数回のAPI呼び出しが正しく処理されることを確認する。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_responses = [
        mocker.Mock(json=lambda: {"transactions": [{"id": 1}]}),
        mocker.Mock(json=lambda: {"transactions": [{"id": 2}]}),
        mocker.Mock(json=lambda: {"transactions": []}),
    ]
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.requests.get",
        side_effect=mock_responses,
    )

    result = get_ton_txns_api.get_transactions_v3("test_account", limit=1)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[1]["id"] == 2


def test_get_transactions_v3_empty_response(mocker: MockerFixture) -> None:
    """
    get_transactions_v3関数の空レスポンステスト。

    空のレスポンスが正しく処理されることを確認する。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_response = mocker.Mock()
    mock_response.json.return_value = {"transactions": []}
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.requests.get",
        return_value=mock_response,
    )

    result = get_ton_txns_api.get_transactions_v3("test_account")

    assert result == []


def test_get_transactions_v3_request_exception(mocker: MockerFixture) -> None:
    """
    get_transactions_v3関数のリクエスト例外テスト。

    リクエスト例外が正しく処理されることを確認する。

    :param mocker: pytest-mockのMockerFixture
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.requests.get",
        side_effect=requests.exceptions.RequestException,
    )

    result = get_ton_txns_api.get_transactions_v3("test_account")

    assert result == []


def test_get_transactions_v3_json_decode_error(mocker: MockerFixture) -> None:
    """
    get_transactions_v3関数のJSONデコードエラーテスト。

    JSONデコードエラーが正しく処理されることを確認する。

    :param mocker: pytest-mockのMockerFixture
    """
    mock_response = mocker.Mock()
    mock_response.json.side_effect = json.JSONDecodeError("Test error", "", 0)
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.requests.get",
        return_value=mock_response,
    )

    result = get_ton_txns_api.get_transactions_v3("test_account")

    assert result == []


def test_main(
    mocker: MockerFixture,
    mock_config: Dict[str, Any],
    mock_transactions: List[Dict[str, Any]],
) -> None:
    """
    main関数のテスト。

    メイン処理が正しく実行されることを確認する。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    :param mock_transactions: モックされたトランザクションデータ
    """
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.load_config",
        return_value=mock_config,
    )
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.get_transactions_v3",
        return_value=mock_transactions,
    )

    captured_output = []
    mocker.patch(
        "builtins.print", lambda *args: captured_output.append(" ".join(map(str, args)))
    )

    get_ton_txns_api.main()

    assert len(captured_output) == 1
    assert "TON Index API v3: Retrieved 2 transactions" in captured_output[0]


def test_main_no_api_key(mocker: MockerFixture, mock_config: Dict[str, Any]) -> None:
    """
    APIキーなしでのmain関数のテスト。

    APIキーがない場合の動作を確認する。

    :param mocker: pytest-mockのMockerFixture
    :param mock_config: モックされた設定データ
    """
    mock_config["ton_api_info"]["api_key"] = ""
    mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.load_config",
        return_value=mock_config,
    )
    mock_get_transactions_v3 = mocker.patch(
        "ton_txns_data_conv.account.get_ton_txns_api.get_transactions_v3",
        return_value=[{"id": 1}],
    )

    captured_output = []
    mocker.patch(
        "builtins.print", lambda *args: captured_output.append(" ".join(map(str, args)))
    )

    get_ton_txns_api.main()

    assert len(captured_output) == 1
    assert "TON Index API v3: Retrieved 1 transactions" in captured_output[0]
    mock_get_transactions_v3.assert_called_once()
