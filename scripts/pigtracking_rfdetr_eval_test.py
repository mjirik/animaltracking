from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
from pytorch_lightning import Trainer

from pigtracking_env_utils import default_device

from rfdetr.config import (
    RFDETRBaseConfig,
    RFDETRLargeConfig,
    RFDETRMediumConfig,
    RFDETRNanoConfig,
    RFDETRSmallConfig,
    TrainConfig,
)
from rfdetr.training.callbacks.coco_eval import COCOEvalCallback
from rfdetr.training.module_data import RFDETRDataModule
from rfdetr.training.module_model import RFDETRModelModule


MODEL_CONFIGS = {
    "nano": RFDETRNanoConfig,
    "small": RFDETRSmallConfig,
    "base": RFDETRBaseConfig,
    "medium": RFDETRMediumConfig,
    "large": RFDETRLargeConfig,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate an RF-DETR checkpoint on the test split.")
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("models") / "pigtracking_rfdetr_best.pth",
        help="Path to the RF-DETR checkpoint_best_total.pth checkpoint.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Path to prepared dataset directory. Defaults to checkpoint args dataset_dir.",
    )
    parser.add_argument(
        "--model-size",
        choices=sorted(MODEL_CONFIGS),
        default="medium",
        help="RF-DETR model size used by the checkpoint.",
    )
    parser.add_argument(
        "--device",
        default=default_device(),
        help="Torch device string, for example cpu, cuda, or cuda:0.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        help="Override test batch size. Defaults to checkpoint args batch_size.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output JSON path. If omitted, a timestamped file is created in runs/eval.",
    )
    return parser.parse_args()


def resolve_output_path(output: Path | None) -> Path:
    if output is not None:
        return output.resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (Path("runs") / "eval" / f"rfdetr_test_eval_{timestamp}.json").resolve()


def torch_device_to_accelerator(device: str) -> tuple[str, int]:
    normalized = device.lower()
    if normalized.startswith("cuda"):
        return "gpu", 1
    if normalized.startswith("mps"):
        return "mps", 1
    return "cpu", 1


def metric_to_jsonable(value: Any) -> float | int | str:
    if isinstance(value, torch.Tensor):
        if value.numel() == 1:
            return float(value.detach().cpu().item())
        return json.dumps(value.detach().cpu().tolist())
    if isinstance(value, (float, int, str)):
        return value
    return str(value)


def main() -> None:
    args = parse_args()
    checkpoint_path = args.checkpoint.resolve()
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    checkpoint_args = checkpoint.get("args") or {}
    if not isinstance(checkpoint_args, dict):
        raise RuntimeError("Checkpoint args were not stored in the expected dict format.")

    dataset_dir = args.dataset.resolve() if args.dataset else Path(checkpoint_args["dataset_dir"]).resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    class_names = checkpoint_args.get("class_names") or []
    num_classes = len(class_names) if class_names else 90

    model_config_class = MODEL_CONFIGS[args.model_size]
    model_config = model_config_class(
        num_classes=num_classes,
        pretrain_weights=None,
        device=args.device,
        compile=False,
    )

    batch_size = args.batch_size or int(checkpoint_args.get("batch_size", 4))
    accelerator, devices = torch_device_to_accelerator(args.device)
    train_config = TrainConfig(
        dataset_dir=str(dataset_dir),
        output_dir=str((Path("runs") / "eval").resolve()),
        batch_size=batch_size,
        grad_accum_steps=1,
        epochs=1,
        dataset_file=str(checkpoint_args.get("dataset_file", "roboflow")),
        class_names=class_names or None,
        num_workers=int(checkpoint_args.get("num_workers", 2)),
        wandb=False,
        tensorboard=False,
        mlflow=False,
        clearml=False,
        progress_bar=None,
        eval_max_dets=int(checkpoint_args.get("eval_max_dets", 500)),
        log_per_class_metrics=bool(checkpoint_args.get("log_per_class_metrics", True)),
        accelerator=accelerator,
        devices=devices,
        use_ema=False,
        compute_test_loss=True,
        compute_val_loss=False,
        run_test=False,
    )

    module = RFDETRModelModule(model_config=model_config, train_config=train_config)
    raw_model = getattr(module.model, "_orig_mod", module.model)
    raw_model.load_state_dict(checkpoint["model"], strict=True)

    datamodule = RFDETRDataModule(model_config=model_config, train_config=train_config)
    trainer = Trainer(
        accelerator=accelerator,
        devices=devices,
        logger=False,
        enable_checkpointing=False,
        callbacks=[
            COCOEvalCallback(
                max_dets=train_config.eval_max_dets,
                segmentation=model_config.segmentation_head,
                eval_interval=1,
                log_per_class_metrics=train_config.log_per_class_metrics,
            )
        ],
        enable_progress_bar=False,
        inference_mode=True,
    )

    test_results = trainer.test(module, datamodule=datamodule, verbose=False)
    callback_metrics = {
        key: metric_to_jsonable(value)
        for key, value in trainer.callback_metrics.items()
        if str(key).startswith("test/")
    }

    payload = {
        "checkpoint": str(checkpoint_path),
        "dataset_dir": str(dataset_dir),
        "model_size": args.model_size,
        "device": args.device,
        "batch_size": batch_size,
        "test_results": test_results,
        "callback_metrics": callback_metrics,
    }

    output_path = resolve_output_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload, indent=2))
    print(f"Saved evaluation to: {output_path}")


if __name__ == "__main__":
    main()
