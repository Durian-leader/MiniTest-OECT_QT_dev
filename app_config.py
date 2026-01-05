import json
import os
import sys
from typing import Any, List, Optional

from logger_config import get_module_logger

logger = get_module_logger()

DEFAULT_BIAS_CURRENT = -1.2868e-6
DEFAULT_BIAS_ENABLED = True
CONFIG_FILENAME = "bias_current.json"


def _config_paths() -> List[str]:
    project_root = os.path.dirname(os.path.abspath(__file__))
    paths = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        paths.append(os.path.join(exe_dir, "resources", "config", CONFIG_FILENAME))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            paths.append(os.path.join(meipass, "resources", "config", CONFIG_FILENAME))
    paths.append(os.path.join(project_root, "resources", "config", CONFIG_FILENAME))
    paths.append(os.path.join(project_root, CONFIG_FILENAME))
    return paths


def _parse_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def load_bias_current_config(path: Optional[str] = None) -> float:
    config_paths = [path] if path else _config_paths()
    data = None
    config_path = None
    for candidate in config_paths:
        try:
            with open(candidate, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            config_path = candidate
            break
        except FileNotFoundError:
            continue
        except Exception as exc:
            logger.warning(f"Failed to load bias current config from {candidate}: {exc}")
            return DEFAULT_BIAS_CURRENT

    if data is None:
        return DEFAULT_BIAS_CURRENT

    enabled = _parse_enabled(data.get("enabled", DEFAULT_BIAS_ENABLED))
    if not enabled:
        return 0.0

    value = data.get("value", DEFAULT_BIAS_CURRENT)
    try:
        return float(value)
    except (TypeError, ValueError):
        if config_path:
            logger.warning(f"Invalid bias current value in {config_path}, using default.")
        return DEFAULT_BIAS_CURRENT


_BIAS_CURRENT = load_bias_current_config()


def get_bias_current() -> float:
    return _BIAS_CURRENT
