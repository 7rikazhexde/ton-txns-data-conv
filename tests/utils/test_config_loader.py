from pathlib import Path
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from ton_txns_data_conv.utils.config_loader import find_config_file, load_config


@pytest.fixture
def mock_project_structure(tmp_path: Path) -> Path:
    """
    プロジェクト構造をモックするフィクスチャ。

    一時ディレクトリにプロジェクトの構造を作成し、テスト用の設定ファイルを配置する。

    :param tmp_path: pytest提供の一時ディレクトリパス
    :return: モックされたプロジェクトのルートディレクトリパス
    """
    project_root = tmp_path / "ton-txns-data-conv"
    utils_dir = project_root / "ton_txns_data_conv" / "utils"
    utils_dir.mkdir(parents=True)
    (utils_dir / "config_loader.py").touch()

    config_dir = project_root / "ton_txns_data_conv"
    config_dir.mkdir(exist_ok=True)

    config_content = """
    [ton_info]
    user_friendly_address = "test_address"
    [cryptact_info]
    counter = "JPY"
    [debug_info]
    enable_tracing = true
    [file_save_option]
    save_allow_json = true
    save_allow_stkrwd = true
    [staking_info]
    staking_calculation_adjustment_value = 5
    local_timezone = 9
    """
    (config_dir / "config.toml").write_text(config_content)
    return project_root


@pytest.fixture
def mock_config_loader(monkeypatch: MonkeyPatch, mock_project_structure: Path) -> Path:
    """
    config_loader.pyの位置をモックするフィクスチャ。

    :param monkeypatch: pytestのmonkeypatchフィクスチャ
    :param mock_project_structure: モックされたプロジェクト構造
    :return: モックされたプロジェクトのルートディレクトリパス
    """

    def mock_resolve(*args: Any, **kwargs: Any) -> Path:
        return (
            mock_project_structure / "ton_txns_data_conv" / "utils" / "config_loader.py"
        )

    monkeypatch.setattr(Path, "resolve", mock_resolve)
    return mock_project_structure


def test_find_config_file_success(mock_config_loader: Path) -> None:
    """
    find_config_file関数が正常に設定ファイルを見つけることをテストする。

    Given: モックされたプロジェクト構造
    When: find_config_file関数を呼び出す
    Then: 正しい設定ファイルのパスが返される
    """
    expected_path = mock_config_loader / "ton_txns_data_conv" / "config.toml"
    assert find_config_file() == expected_path


def test_find_config_file_not_found(
    mock_config_loader: Path, monkeypatch: MonkeyPatch
) -> None:
    """
    設定ファイルが見つからない場合にfind_config_file関数が例外を発生させることをテストする。

    Given: 設定ファイルが存在しないモック環境
    When: find_config_file関数を呼び出す
    Then: FileNotFoundError例外が発生する
    """

    def mock_exists(*args: Any, **kwargs: Any) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", mock_exists)
    with pytest.raises(FileNotFoundError):
        find_config_file()


def test_find_config_file_custom_name(mock_config_loader: Path) -> None:
    """
    find_config_file関数がカスタム名の設定ファイルを見つけることをテストする。

    Given: カスタム名の設定ファイルを含むモック環境
    When: カスタム名でfind_config_file関数を呼び出す
    Then: カスタム名の設定ファイルのパスが返される
    """
    custom_config = mock_config_loader / "ton_txns_data_conv" / "custom_config.toml"
    custom_config.touch()
    assert find_config_file("custom_config.toml") == custom_config


def test_load_config_success(mock_config_loader: Path) -> None:
    """
    load_config関数が正常に設定を読み込むことをテストする。

    Given: 有効な設定ファイルを含むモック環境
    When: load_config関数を呼び出す
    Then: 設定が正しく読み込まれ、期待される値が含まれている
    """
    config = load_config()
    assert isinstance(config, dict)
    assert config["ton_info"]["user_friendly_address"] == "test_address"
    assert config["cryptact_info"]["counter"] == "JPY"
    assert config["debug_info"]["enable_tracing"] is True
    assert config["file_save_option"]["save_allow_json"] is True
    assert config["file_save_option"]["save_allow_stkrwd"] is True
    assert config["staking_info"]["staking_calculation_adjustment_value"] == 5
    assert config["staking_info"]["local_timezone"] == 9


def test_load_config_file_not_found(monkeypatch: MonkeyPatch) -> None:
    """
    設定ファイルが見つからない場合にload_config関数が例外を発生させることをテストする。

    Given: 設定ファイルが存在しないモック環境
    When: load_config関数を呼び出す
    Then: FileNotFoundError例外が発生する
    """

    def mock_find_config_file(*args: Any, **kwargs: Any) -> None:
        raise FileNotFoundError("Test error")

    monkeypatch.setattr(
        "ton_txns_data_conv.utils.config_loader.find_config_file", mock_find_config_file
    )
    with pytest.raises(FileNotFoundError):
        load_config()


def test_load_config_invalid_toml(
    mock_config_loader: Path, monkeypatch: MonkeyPatch
) -> None:
    """
    無効なTOML内容の設定ファイルを読み込もうとした場合にload_config関数が例外を発生させることをテストする。

    Given: 無効なTOML内容を持つ設定ファイルを含むモック環境
    When: load_config関数を呼び出す
    Then: 例外が発生する
    """
    invalid_config = mock_config_loader / "ton_txns_data_conv" / "invalid_config.toml"
    invalid_config.write_text("invalid toml content")
    monkeypatch.setattr(
        "ton_txns_data_conv.utils.config_loader.find_config_file",
        lambda *args: invalid_config,
    )
    with pytest.raises(Exception):
        load_config()


def test_load_config_empty_file(
    mock_config_loader: Path, monkeypatch: MonkeyPatch
) -> None:
    """
    空の設定ファイルを読み込んだ場合にload_config関数が空の辞書を返すことをテストする。

    Given: 空の設定ファイルを含むモック環境
    When: load_config関数を呼び出す
    Then: 空の辞書が返される
    """
    empty_config = mock_config_loader / "ton_txns_data_conv" / "empty_config.toml"
    empty_config.write_text("")
    monkeypatch.setattr(
        "ton_txns_data_conv.utils.config_loader.find_config_file",
        lambda *args: empty_config,
    )
    config = load_config()
    assert isinstance(config, dict)
    assert len(config) == 0
