from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

import rfdetr

from pigtracking_env_utils import default_device


MODEL_CLASSES = {
    "nano": "RFDETRNano",
    "small": "RFDETRSmall",
    "base": "RFDETRBase",
    "medium": "RFDETRMedium",
    "large": "RFDETRLarge",
}
SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RF-DETR inference over pigtracking images.")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models") / "pigtracking_rfdetr_best.pth",
        help="Path to a trained RF-DETR checkpoint.",
    )
    parser.add_argument(
        "--model-size",
        default="nano",
        choices=sorted(MODEL_CLASSES),
        help="RF-DETR model size used by the checkpoint.",
    )
    parser.add_argument("--input", type=Path, required=True, help="Folder with input images.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. If omitted, a timestamped directory is created in runs/predict.",
    )
    parser.add_argument(
        "--class-map",
        type=Path,
        default=Path("models") / "pigtracking_rfdetr_best.classes.json",
        help="JSON mapping from RF-DETR class/category id to class name.",
    )
    parser.add_argument("--threshold", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument(
        "--device",
        default=default_device(),
        help="Device passed to RF-DETR, for example cpu, cuda, cuda:0, or mps.",
    )
    return parser.parse_args()


def resolve_output_dir(output: Path | None) -> Path:
    if output is not None:
        return output.resolve()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (Path("runs") / "predict" / f"rfdetr_pigtracking_{timestamp}").resolve()


def build_model(model_size: str, checkpoint: Path, device: str, num_classes: int | None) -> Any:
    class_name = MODEL_CLASSES[model_size]
    try:
        model_class = getattr(rfdetr, class_name)
    except (AttributeError, ImportError) as exc:
        raise RuntimeError(
            f"Installed rfdetr package does not provide {class_name}. "
            "Try another --model-size or update rfdetr."
        ) from exc

    kwargs: dict[str, Any] = {
        "pretrain_weights": str(checkpoint),
        "device": device,
    }
    if num_classes is not None:
        kwargs["num_classes"] = num_classes

    model = model_class(**kwargs)
    optimize_for_inference = getattr(model, "optimize_for_inference", None)
    if callable(optimize_for_inference):
        optimize_for_inference()
    return model


def load_class_map(path: Path) -> dict[int, str]:
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(key): str(value) for key, value in data.items()}


def class_name_for_id(class_id: int | None, class_map: dict[int, str]) -> str | None:
    if class_id is None:
        return None
    if class_id in class_map:
        return class_map[class_id]
    if class_id == 0 or (0 not in class_map and (class_id + 1) in class_map):
        return class_map.get(class_id + 1)
    return None


def image_paths(input_dir: Path) -> list[Path]:
    candidates = input_dir.rglob("*")
    return sorted(
        path for path in candidates if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def load_rgb_image(image_path: Path) -> Image.Image:
    with Image.open(image_path) as image:
        return image.convert("RGB")


def detection_rows(detections: Any, threshold: float) -> list[dict[str, Any]]:
    xyxy_values = getattr(detections, "xyxy", [])
    confidence_values = getattr(detections, "confidence", None)
    class_id_values = getattr(detections, "class_id", None)

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

        x1, y1, x2, y2 = [float(value) for value in xyxy]
        rows.append(
            {
                "bbox_xyxy": [x1, y1, x2, y2],
                "confidence": confidence,
                "class_id": class_id,
            }
        )
    return rows


def label_for(row: dict[str, Any], class_map: dict[int, str]) -> str:
    class_id = row["class_id"]
    if class_id is None:
        label = "object"
    else:
        label = class_name_for_id(class_id, class_map) or f"class_{class_id}"

    confidence = row["confidence"]
    if confidence is None:
        return label
    return f"{label} {confidence:.2f}"


def draw_predictions(
    image_path: Path,
    output_path: Path,
    rows: list[dict[str, Any]],
    class_map: dict[int, str],
) -> None:
    with Image.open(image_path) as image:
        annotated = image.convert("RGB")

    draw = ImageDraw.Draw(annotated)
    for row in rows:
        x1, y1, x2, y2 = row["bbox_xyxy"]
        label = label_for(row, class_map)
        draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
        text_bbox = draw.textbbox((x1, y1), label)
        draw.rectangle(text_bbox, fill="red")
        draw.text((x1, y1), label, fill="white")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    annotated.save(output_path)


def main() -> None:
    args = parse_args()
    model_path = args.model.resolve()
    input_dir = args.input.resolve()
    output_dir = resolve_output_dir(args.output)
    class_map = load_class_map(args.class_map.resolve())
    num_classes = max(class_map) if class_map else None

    if not model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    paths = image_paths(input_dir)
    if not paths:
        raise ValueError(f"No supported images found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = build_model(args.model_size, model_path, args.device, num_classes)

    predictions: list[dict[str, Any]] = []
    for image_path in paths:
        detections = model.predict(load_rgb_image(image_path))
        rows = detection_rows(detections, args.threshold)

        relative_path = image_path.relative_to(input_dir)
        output_path = output_dir / relative_path
        draw_predictions(image_path, output_path, rows, class_map)

        predictions.append(
            {
                "image": str(image_path),
                "output": str(output_path),
                "detections": [
                    {
                        **row,
                        "class_name": class_name_for_id(row["class_id"], class_map),
                    }
                    for row in rows
                ],
            }
        )

    predictions_path = output_dir / "predictions.json"
    predictions_path.write_text(
        json.dumps(predictions, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Inference outputs saved to: {output_dir}")
    print(f"Predictions JSON: {predictions_path}")


if __name__ == "__main__":
    main()
