from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import rfdetr

from .env_config import project_root


MODEL_CLASSES = {
    "nano": "RFDETRNano",
    "small": "RFDETRSmall",
    "base": "RFDETRBase",
    "medium": "RFDETRMedium",
    "large": "RFDETRLarge",
}


def default_device() -> str:
    return os.environ.get("RFDETR_DEVICE", "cuda")


def model_path() -> Path:
    return project_root() / "models" / "pigtracking_rfdetr_best.pth"


def class_map_path() -> Path:
    return project_root() / "models" / "pigtracking_rfdetr_best.classes.json"


def load_class_map(path: Path | None = None) -> dict[int, str]:
    resolved = path or class_map_path()
    if not resolved.exists():
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    return {int(key): str(value) for key, value in data.items()}


def build_model(
    model_size: str = "nano",
    checkpoint: Path | None = None,
    device: str | None = None,
    num_classes: int | None = None,
) -> Any:
    checkpoint_path = checkpoint or model_path()
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")

    class_name = MODEL_CLASSES[model_size]
    try:
        model_class = getattr(rfdetr, class_name)
    except (AttributeError, ImportError) as exc:
        raise RuntimeError(
            f"Installed rfdetr package does not provide {class_name}. "
            "Try another model size or update rfdetr."
        ) from exc

    kwargs: dict[str, Any] = {
        "pretrain_weights": str(checkpoint_path),
        "device": device or default_device(),
    }
    if num_classes is not None:
        kwargs["num_classes"] = num_classes

    model = model_class(**kwargs)
    optimize_for_inference = getattr(model, "optimize_for_inference", None)
    if callable(optimize_for_inference):
        optimize_for_inference()
    return model


def detection_rows(detections: Any, threshold: float) -> list[dict[str, Any]]:
    xyxy_values = getattr(detections, "xyxy", [])
    confidence_values = getattr(detections, "confidence", None)
    class_id_values = getattr(detections, "class_id", None)
    tracker_id_values = getattr(detections, "tracker_id", None)

    rows: list[dict[str, Any]] = []
    for index, xyxy in enumerate(xyxy_values):
        confidence = None
        if confidence_values is not None:
            confidence = float(confidence_values[index])
            if confidence < threshold:
                continue

        class_id = None
        if class_id_values is not None:
            class_id = int(class_id_values[index])

        tracker_id = None
        if tracker_id_values is not None:
            tracker_id = int(tracker_id_values[index])
            if tracker_id < 0:
                tracker_id = None

        x1, y1, x2, y2 = [float(value) for value in xyxy]
        rows.append(
            {
                "bbox_xyxy": [x1, y1, x2, y2],
                "confidence": confidence,
                "class_id": class_id,
                "tracker_id": tracker_id,
            }
        )
    return rows


def class_name_for_id(class_id: int | None, class_map: dict[int, str]) -> str | None:
    if class_id is None:
        return None
    if class_id in class_map:
        return class_map[class_id]
    if class_id == 0 or (0 not in class_map and (class_id + 1) in class_map):
        return class_map.get(class_id + 1)
    return None


def label_for(row: dict[str, Any], class_map: dict[int, str]) -> str:
    class_id = row["class_id"]
    if class_id is None:
        label = "object"
    else:
        label = class_name_for_id(class_id, class_map) or f"class_{class_id}"

    tracker_id = row.get("tracker_id")
    if tracker_id is not None:
        label = f"{label} #{tracker_id}"

    confidence = row["confidence"]
    if confidence is None:
        return label
    return f"{label} {confidence:.2f}"


def draw_predictions(
    image: Image.Image,
    rows: list[dict[str, Any]],
    class_map: dict[int, str],
) -> Image.Image:
    annotated = image.copy().convert("RGB")
    draw = ImageDraw.Draw(annotated)
    for row in rows:
        x1, y1, x2, y2 = row["bbox_xyxy"]
        label = label_for(row, class_map)
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        text_bbox = draw.textbbox((x1, y1), label)
        draw.rectangle(text_bbox, fill="red")
        draw.text((x1, y1), label, fill="white")
    return annotated
