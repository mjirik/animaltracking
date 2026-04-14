from __future__ import annotations

import os
from pathlib import Path


DEFAULT_CVAT_DATASET_ENV = "PIGTRACKING_CVAT_DATASET"
DEFAULT_OUTPUT_DATASET_ENV = "PIGTRACKING_RFDETR_DATASET"
DEFAULT_DEVICE_ENV = "RFDETR_DEVICE"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def env_file_path() -> Path:
    return project_root() / ".env"


def load_env_file(path: Path | None = None) -> dict[str, str]:
    env_path = path or env_file_path()
    values: dict[str, str] = {}
    if not env_path.exists():
        return values

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def env_value(name: str) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    return load_env_file().get(name)


def default_dataset_path() -> Path | None:
    value = env_value(DEFAULT_CVAT_DATASET_ENV)
    return Path(value) if value else None


def default_rfdetr_output_path() -> Path | None:
    value = env_value(DEFAULT_OUTPUT_DATASET_ENV)
    return Path(value) if value else None


def default_device() -> str:
    return env_value(DEFAULT_DEVICE_ENV) or "cuda"


def require_source_path(source: Path | None) -> Path:
    if source is None:
        raise ValueError(
            "Missing dataset source. Pass --source or set "
            f"{DEFAULT_CVAT_DATASET_ENV} in .env."
        )
    return source.resolve()
