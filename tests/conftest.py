from pathlib import Path
from typing import Any


def pytest_ignore_collect(collection_path: Path, config: Any) -> bool:
    """
    特定のファイルをテスト収集から除外するための pytest フック関数。

    この関数は、pytest がテストを収集する際に各ファイルに対して呼び出されます。
    'ton_txns_data_conv/staking/ton_whales_staking_dashboard.py' ファイルを
    テスト対象から除外するために使用されます。

    注意: このファイルはカバレッジレポートからも除外されています（pyproject.toml の設定による）。

    Args:
        collection_path (Path): チェック対象のファイルパス
        config (Any): pytest の設定オブジェクト（この関数では使用しない）

    Returns:
        bool: 指定されたパスが除外対象の場合は True、そうでない場合は False
    """
    excluded_file = Path("ton_txns_data_conv/staking/ton_whales_staking_dashboard.py")
    return excluded_file.parts[-3:] == collection_path.parts[-3:]
