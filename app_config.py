import json
import os
import sys
from typing import Any, List, Optional

from logger_config import get_module_logger

logger = get_module_logger()

DEFAULT_BIAS_CURRENT = -1.2868e-6
DEFAULT_BIAS_ENABLED = True
DEFAULT_REFERENCE_TRANSIMPEDANCE = 100.0
CONFIG_FILENAME = "bias_current.json"

# Performance tuning defaults
PERFORMANCE_CONFIG_FILENAME = "performance_config.json"
DEFAULT_SERIAL_READ_CHUNK_SIZE = 4096
DEFAULT_BUFFER_FLUSH_PACKET_COUNT = 200
DEFAULT_BUFFER_FLUSH_INTERVAL_SEC = 0.2
DEFAULT_INCREMENTAL_SAVE_INTERVAL_SEC = 5.0


def _config_paths_for(filename: str) -> List[str]:
    project_root = os.path.dirname(os.path.abspath(__file__))
    paths = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(sys.executable)
        paths.append(os.path.join(exe_dir, "resources", "config", filename))
        meipass = getattr(sys, "_MEIPASS", "")
        if meipass:
            paths.append(os.path.join(meipass, "resources", "config", filename))
    paths.append(os.path.join(project_root, "resources", "config", filename))
    paths.append(os.path.join(project_root, filename))
    return paths


def _parse_enabled(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def load_bias_current_config(path: Optional[str] = None) -> tuple:
    """Load bias current config and return (bias_current, reference_transimpedance)."""
    config_paths = [path] if path else _config_paths_for(CONFIG_FILENAME)
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
            return DEFAULT_BIAS_CURRENT, DEFAULT_REFERENCE_TRANSIMPEDANCE

    if data is None:
        return DEFAULT_BIAS_CURRENT, DEFAULT_REFERENCE_TRANSIMPEDANCE

    enabled = _parse_enabled(data.get("enabled", DEFAULT_BIAS_ENABLED))
    if not enabled:
        return 0.0, DEFAULT_REFERENCE_TRANSIMPEDANCE

    # Parse bias current value
    value = data.get("value", DEFAULT_BIAS_CURRENT)
    try:
        bias_current = float(value)
    except (TypeError, ValueError):
        if config_path:
            logger.warning(f"Invalid bias current value in {config_path}, using default.")
        bias_current = DEFAULT_BIAS_CURRENT

    # Parse reference transimpedance
    ref_trans = data.get("reference_transimpedance", DEFAULT_REFERENCE_TRANSIMPEDANCE)
    try:
        reference_transimpedance = float(ref_trans)
        if reference_transimpedance <= 0:
            reference_transimpedance = DEFAULT_REFERENCE_TRANSIMPEDANCE
    except (TypeError, ValueError):
        if config_path:
            logger.warning(f"Invalid reference_transimpedance in {config_path}, using default.")
        reference_transimpedance = DEFAULT_REFERENCE_TRANSIMPEDANCE

    return bias_current, reference_transimpedance


_BIAS_CURRENT, _BIAS_REFERENCE_TRANSIMPEDANCE = load_bias_current_config()


def load_performance_config(path: Optional[str] = None) -> tuple:
    """Load performance tuning config: (read_chunk, buffer_packet_count, buffer_flush_interval, incremental_save_interval)."""
    config_paths = [path] if path else _config_paths_for(PERFORMANCE_CONFIG_FILENAME)
    data = None
    for candidate in config_paths:
        try:
            with open(candidate, "r", encoding="utf-8") as file_handle:
                data = json.load(file_handle)
            break
        except FileNotFoundError:
            continue
        except Exception as exc:
            logger.warning(f"Failed to load performance config from {candidate}: {exc}")
            return (
                DEFAULT_SERIAL_READ_CHUNK_SIZE,
                DEFAULT_BUFFER_FLUSH_PACKET_COUNT,
                DEFAULT_BUFFER_FLUSH_INTERVAL_SEC,
                DEFAULT_INCREMENTAL_SAVE_INTERVAL_SEC,
            )

    if data is None:
        return (
            DEFAULT_SERIAL_READ_CHUNK_SIZE,
            DEFAULT_BUFFER_FLUSH_PACKET_COUNT,
            DEFAULT_BUFFER_FLUSH_INTERVAL_SEC,
            DEFAULT_INCREMENTAL_SAVE_INTERVAL_SEC,
        )

    def _parse_int(value, default):
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def _parse_float(value, default):
        try:
            parsed = float(value)
            return parsed if parsed > 0 else default
        except Exception:
            return default

    read_chunk = _parse_int(data.get("serial_read_chunk_size"), DEFAULT_SERIAL_READ_CHUNK_SIZE)
    packet_count = _parse_int(data.get("buffer_flush_packet_count"), DEFAULT_BUFFER_FLUSH_PACKET_COUNT)
    flush_interval = _parse_float(
        data.get("buffer_flush_interval_sec"),
        DEFAULT_BUFFER_FLUSH_INTERVAL_SEC,
    )
    incremental_save_interval = _parse_float(
        data.get("incremental_save_interval_sec"),
        DEFAULT_INCREMENTAL_SAVE_INTERVAL_SEC,
    )

    return read_chunk, packet_count, flush_interval, incremental_save_interval


_PERF_READ_CHUNK, _PERF_PACKET_COUNT, _PERF_FLUSH_INTERVAL, _PERF_INCREMENTAL_SAVE_INTERVAL = load_performance_config()


def get_bias_current() -> float:
    return _BIAS_CURRENT


def get_bias_reference_transimpedance() -> float:
    return _BIAS_REFERENCE_TRANSIMPEDANCE


def get_serial_read_chunk_size() -> int:
    return _PERF_READ_CHUNK


def get_buffer_flush_packet_count() -> int:
    return _PERF_PACKET_COUNT


def get_buffer_flush_interval_sec() -> float:
    return _PERF_FLUSH_INTERVAL


def get_incremental_save_interval_sec() -> float:
    return _PERF_INCREMENTAL_SAVE_INTERVAL
