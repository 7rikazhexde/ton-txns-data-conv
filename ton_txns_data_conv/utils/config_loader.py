from pathlib import Path
from typing import Any, Dict

from tomlkit import TOMLDocument, parse


def find_config_file(file_name: str = "config.toml") -> Path:
    current_dir = Path(__file__).resolve().parent
    while current_dir != current_dir.parent:
        config_path = current_dir / file_name
        if config_path.exists():
            return config_path
        current_dir = current_dir.parent
    raise FileNotFoundError(
        f"Configuration file '{file_name}' not found in the project directory or its parents."
    )


def load_config() -> Dict[str, Any]:
    config_file_path = find_config_file()
    try:
        with open(config_file_path, "r") as config_file:
            config: TOMLDocument = parse(config_file.read())
        return dict(config)
    except Exception as e:
        print(f"Error: Failed to read configuration file. {str(e)}")
        raise
