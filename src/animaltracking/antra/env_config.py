from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


ROI_VALUE_COUNT = 4
PEN_PATTERN = re.compile(
    r"^RTSP_CAM(?P<camera_id>\d+)_PEN(?P<pen_index>\d+)_ROI_XYXY_NORM_IN_CAMROI$"
)


@dataclass(frozen=True)
class PenEnvConfig:
    camera_id: int
    pen_index: int
    key: str
    name: str
    roi_xyxy_norm_in_camroi: tuple[float, float, float, float]


@dataclass(frozen=True)
class CameraEnvConfig:
    camera_id: int
    camera_roi_xyxy_norm: tuple[float, float, float, float] | None
    pens: tuple[PenEnvConfig, ...]


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_dotenv(path: Path | None = None) -> dict[str, str]:
    env_path = path or (project_root() / ".env")
    data: dict[str, str] = {}
    if not env_path.exists():
        return data

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        data[key] = value
        os.environ.setdefault(key, value)
    return data


def parse_roi(value: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != ROI_VALUE_COUNT:
        raise ValueError(f"ROI must contain {ROI_VALUE_COUNT} comma-separated floats: {value}")
    roi = tuple(float(part) for part in parts)
    x1, y1, x2, y2 = roi
    if not (0.0 <= x1 < x2 <= 1.0 and 0.0 <= y1 < y2 <= 1.0):
        raise ValueError(f"ROI must satisfy 0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1: {value}")
    return roi


def parse_camera_configs(env: dict[str, str] | None = None) -> list[CameraEnvConfig]:
    config = dict(os.environ)
    if env:
        config.update(env)

    cameras: dict[int, dict[str, object]] = {}
    for key, value in config.items():
        pen_match = PEN_PATTERN.match(key)
        if pen_match:
            camera_id = int(pen_match.group("camera_id"))
            pen_index = int(pen_match.group("pen_index"))
            camera_entry = cameras.setdefault(camera_id, {"camera_roi": None, "pens": []})
            pen_name_key = f"RTSP_CAM{camera_id}_PEN{pen_index}_NAME"
            pen_name = config.get(pen_name_key, f"Camera {camera_id} Pen {pen_index}")
            camera_entry["pens"].append(
                PenEnvConfig(
                    camera_id=camera_id,
                    pen_index=pen_index,
                    key=f"cam{camera_id}_pen{pen_index}",
                    name=pen_name,
                    roi_xyxy_norm_in_camroi=parse_roi(value),
                )
            )
            continue

        roi_prefix = "RTSP_CAM"
        roi_suffix = "_ROI_XYXY_NORM"
        if key.startswith(roi_prefix) and key.endswith(roi_suffix):
            camera_id = int(key[len(roi_prefix) : -len(roi_suffix)])
            camera_entry = cameras.setdefault(camera_id, {"camera_roi": None, "pens": []})
            camera_entry["camera_roi"] = parse_roi(value)

    configs: list[CameraEnvConfig] = []
    for camera_id in sorted(cameras):
        raw_pens = cameras[camera_id]["pens"]
        pens = tuple(sorted(raw_pens, key=lambda pen: pen.pen_index))
        configs.append(
            CameraEnvConfig(
                camera_id=camera_id,
                camera_roi_xyxy_norm=cameras[camera_id]["camera_roi"],
                pens=pens,
            )
        )
    return configs
