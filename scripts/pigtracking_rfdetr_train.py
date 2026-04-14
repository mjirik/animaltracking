from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from pigtracking_env_utils import default_device, default_rfdetr_output_path

import rfdetr


MODEL_CLASSES = {
    "nano": "RFDETRNano",
    "small": "RFDETRSmall",
    "base": "RFDETRBase",
    "medium": "RFDETRMedium",
    "large": "RFDETRLarge",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train an RF-DETR model on the pigtracking dataset.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=default_rfdetr_output_path() or Path("data") / "pigtracking_rfdetr",
        help="Path to a prepared RF-DETR dataset directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. If omitted, a timestamped directory is created in runs/train.",
    )
    parser.add_argument(
        "--model-size",
        default="medium",
        choices=sorted(MODEL_CLASSES),
        help="RF-DETR model size to fine-tune.",
    )
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=4, help="Training batch size.")
    parser.add_argument(
        "--grad-accum-steps",
        type=int,
        default=4,
        help="Gradient accumulation steps.",
    )
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate.")
    parser.add_argument(
        "--resolution",
        type=int,
        help="Input resolution. RF-DETR requires values divisible by 14.",
    )
    parser.add_argument(
        "--device",
        default=default_device(),
        help="Device passed to RF-DETR, for example cpu, cuda, cuda:0, or mps.",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Checkpoint to resume training from.",
    )
    parser.add_argument(
        "--stable-output",
        type=Path,
        default=Path("models") / "pigtracking_rfdetr_best.pth",
        help="Stable path where checkpoint_best_total.pth is copied after training.",
    )
    return parser.parse_args()


def resolve_output_dir(output: Path | None) -> Path:
    if output is not None:
        return output.resolve()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (Path("runs") / "train" / f"rfdetr_pigtracking_{timestamp}").resolve()


def build_model(model_size: str, device: str) -> Any:
    class_name = MODEL_CLASSES[model_size]
    try:
        model_class = getattr(rfdetr, class_name)
    except (AttributeError, ImportError) as exc:
        raise RuntimeError(
            f"Installed rfdetr package does not provide {class_name}. "
            "Try another --model-size or update rfdetr."
        ) from exc
    return model_class(device=device)


def copy_if_exists(source: Path, destination: Path) -> None:
    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    args = parse_args()
    dataset_dir = args.dataset.resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not (dataset_dir / "train" / "_annotations.coco.json").exists():
        raise FileNotFoundError(
            "Dataset format was not recognized. Expected train/_annotations.coco.json."
        )

    output_dir = resolve_output_dir(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    train_kwargs: dict[str, Any] = {
        "dataset_dir": str(dataset_dir),
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "grad_accum_steps": args.grad_accum_steps,
        "lr": args.lr,
        "output_dir": str(output_dir),
        "device": args.device,
    }
    if args.resolution is not None:
        train_kwargs["resolution"] = args.resolution
    if args.resume is not None:
        train_kwargs["resume"] = str(args.resume.resolve())

    model = build_model(args.model_size, args.device)
    model.train(**train_kwargs)

    best_checkpoint = output_dir / "checkpoint_best_total.pth"
    if not best_checkpoint.exists():
        raise FileNotFoundError(
            f"Training finished, but the expected best checkpoint was not found: {best_checkpoint}"
        )

    stable_output = args.stable_output.resolve()
    stable_output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_checkpoint, stable_output)

    class_map_path = dataset_dir / "class_names.json"
    stable_class_map = stable_output.with_suffix(".classes.json")
    copy_if_exists(class_map_path, stable_class_map)
    copy_if_exists(class_map_path, output_dir / "class_names.json")

    metadata = {
        "model_size": args.model_size,
        "dataset": str(dataset_dir),
        "checkpoint": str(stable_output),
        "class_map": str(stable_class_map) if stable_class_map.exists() else None,
        "device": args.device,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "grad_accum_steps": args.grad_accum_steps,
        "lr": args.lr,
        "resolution": args.resolution,
    }
    (stable_output.with_suffix(".metadata.json")).write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Training completed. Run directory: {output_dir}")
    print(f"Best checkpoint: {best_checkpoint}")
    print(f"Stable checkpoint: {stable_output}")
    if stable_class_map.exists():
        print(f"Stable class map: {stable_class_map}")


if __name__ == "__main__":
    main()
