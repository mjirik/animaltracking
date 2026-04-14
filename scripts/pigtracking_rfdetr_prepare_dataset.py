from __future__ import annotations

import argparse
import json
import random
import shutil
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any

from pigtracking_env_utils import (
    default_dataset_path,
    default_rfdetr_output_path,
    require_source_path,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare an RF-DETR COCO dataset from a pigtracking CVAT export."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=default_dataset_path(),
        help=(
            "Path to the extracted CVAT export directory with images/ and annotations.xml. "
            "Defaults to PIGTRACKING_CVAT_DATASET from .env."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_rfdetr_output_path() or Path("data") / "pigtracking_rfdetr",
        help="Where to write the prepared RF-DETR dataset.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for splitting.")
    parser.add_argument("--train-ratio", type=float, default=0.7, help="Train split ratio.")
    parser.add_argument(
        "--valid-ratio",
        type=float,
        default=0.2,
        help="Validation split ratio. The rest goes to test.",
    )
    parser.add_argument(
        "--labels",
        nargs="+",
        default=["pig"],
        help="Labels to include from the CVAT export. Defaults to pig.",
    )
    return parser.parse_args()


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(value, upper))


def split_items(
    items: list[dict[str, Any]], train_ratio: float, valid_ratio: float
) -> dict[str, list[dict[str, Any]]]:
    if not items:
        return {"train": [], "valid": [], "test": []}

    total = len(items)
    train_count = int(round(total * train_ratio))
    valid_count = int(round(total * valid_ratio))

    if total >= 3:
        train_count = max(1, min(train_count, total - 2))
        valid_count = max(1, min(valid_count, total - train_count - 1))
    else:
        train_count = max(1, total - 1)
        valid_count = max(0, total - train_count)

    test_count = total - train_count - valid_count
    if total >= 3 and test_count < 1:
        if train_count >= valid_count and train_count > 1:
            train_count -= 1
        elif valid_count > 1:
            valid_count -= 1

    return {
        "train": items[:train_count],
        "valid": items[train_count : train_count + valid_count],
        "test": items[train_count + valid_count :],
    }


def read_labels(root: ET.Element) -> list[str]:
    labels = [node.findtext("name", default="") for node in root.findall(".//labels/label")]
    labels = [label for label in labels if label]
    if not labels:
        raise ValueError("No labels were found in the CVAT XML.")
    return labels


def build_image_lookup(images_dir: Path) -> dict[str, Path]:
    lookup: dict[str, Path] = {}
    for path in images_dir.rglob("*"):
        if path.is_file():
            relative = path.relative_to(images_dir).as_posix()
            lookup[relative] = path
    return lookup


def find_image_path(image_name: str, image_lookup: dict[str, Path]) -> Path:
    direct = image_lookup.get(image_name)
    if direct is not None:
        return direct

    suffix = "/" + image_name
    matches = [
        path for relative, path in image_lookup.items() if relative == image_name or relative.endswith(suffix)
    ]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"Missing image referenced by XML: {image_name}")
    raise ValueError(f"Multiple images matched XML name {image_name!r}: {matches}")


def parse_samples(
    root: ET.Element,
    images_dir: Path,
    label_to_category_id: dict[str, int],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    samples: list[dict[str, Any]] = []
    class_counter: Counter[str] = Counter()
    image_lookup = build_image_lookup(images_dir)

    for image_node in root.findall(".//image"):
        image_id = int(image_node.attrib["id"])
        image_name = image_node.attrib["name"]
        image_path = find_image_path(image_name, image_lookup)

        width = float(image_node.attrib["width"])
        height = float(image_node.attrib["height"])
        annotations: list[dict[str, Any]] = []

        for box_node in image_node.findall("box"):
            label = box_node.attrib["label"]
            category_id = label_to_category_id.get(label)
            if category_id is None:
                continue

            xtl = clamp(float(box_node.attrib["xtl"]), 0.0, width)
            ytl = clamp(float(box_node.attrib["ytl"]), 0.0, height)
            xbr = clamp(float(box_node.attrib["xbr"]), 0.0, width)
            ybr = clamp(float(box_node.attrib["ybr"]), 0.0, height)
            box_width = max(0.0, xbr - xtl)
            box_height = max(0.0, ybr - ytl)
            if box_width <= 0.0 or box_height <= 0.0:
                continue

            annotations.append(
                {
                    "category_id": category_id,
                    "bbox": [xtl, ytl, box_width, box_height],
                    "area": box_width * box_height,
                    "iscrowd": 0,
                }
            )
            class_counter[label] += 1

        if not annotations:
            continue

        file_name = image_path.relative_to(images_dir).as_posix()
        samples.append(
            {
                "image_id": image_id,
                "file_name": file_name,
                "image_path": image_path,
                "width": int(round(width)),
                "height": int(round(height)),
                "annotations": annotations,
            }
        )

    return samples, class_counter


def write_coco_split(
    split_dir: Path,
    split_samples: list[dict[str, Any]],
    categories: list[dict[str, Any]],
) -> None:
    split_dir.mkdir(parents=True, exist_ok=True)

    images: list[dict[str, Any]] = []
    annotations: list[dict[str, Any]] = []
    annotation_id = 1

    for sample in split_samples:
        destination = split_dir / sample["file_name"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample["image_path"], destination)

        images.append(
            {
                "id": sample["image_id"],
                "file_name": sample["file_name"],
                "width": sample["width"],
                "height": sample["height"],
            }
        )

        for annotation in sample["annotations"]:
            annotations.append(
                {
                    "id": annotation_id,
                    "image_id": sample["image_id"],
                    "category_id": annotation["category_id"],
                    "bbox": annotation["bbox"],
                    "area": annotation["area"],
                    "iscrowd": annotation["iscrowd"],
                }
            )
            annotation_id += 1

    coco = {
        "info": {
            "description": "Pigtracking dataset prepared from CVAT for RF-DETR",
            "version": "1.0",
        },
        "licenses": [],
        "categories": categories,
        "images": images,
        "annotations": annotations,
    }
    annotations_path = split_dir / "_annotations.coco.json"
    annotations_path.write_text(
        json.dumps(coco, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_data_yaml(output_dir: Path, labels: list[str]) -> None:
    yaml_lines = [
        f"path: {output_dir.as_posix()}",
        "train: train",
        "val: valid",
        "test: test",
        f"nc: {len(labels)}",
        "names:",
    ]
    yaml_lines.extend(f"  - \"{label}\"" for label in labels)
    (output_dir / "data.yaml").write_text("\n".join(yaml_lines) + "\n", encoding="utf-8")
    class_names = {str(index + 1): label for index, label in enumerate(labels)}
    (output_dir / "class_names.json").write_text(
        json.dumps(class_names, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def validate_ratios(train_ratio: float, valid_ratio: float) -> None:
    if not 0.0 < train_ratio < 1.0:
        raise ValueError("--train-ratio must be between 0 and 1.")
    if not 0.0 <= valid_ratio < 1.0:
        raise ValueError("--valid-ratio must be between 0 and 1.")
    if train_ratio + valid_ratio >= 1.0:
        raise ValueError("--train-ratio + --valid-ratio must be less than 1.0.")


def main() -> None:
    args = parse_args()
    validate_ratios(args.train_ratio, args.valid_ratio)

    source_dir = require_source_path(args.source)
    output_dir = args.output.resolve()
    annotations_path = source_dir / "annotations.xml"
    images_dir = source_dir / "images"

    if not annotations_path.exists():
        raise FileNotFoundError(f"Missing annotations file: {annotations_path}")
    if not images_dir.exists():
        raise FileNotFoundError(f"Missing images directory: {images_dir}")

    root = ET.parse(annotations_path).getroot()
    available_labels = read_labels(root)
    labels = [label for label in args.labels if label in available_labels]
    if not labels:
        raise ValueError(
            "None of the requested labels were found in the CVAT XML. "
            f"Available labels: {available_labels}"
        )
    categories = [
        {"id": index + 1, "name": label, "supercategory": "pigtracking"}
        for index, label in enumerate(labels)
    ]
    label_to_category_id = {label: index + 1 for index, label in enumerate(labels)}

    samples, class_counter = parse_samples(root, images_dir, label_to_category_id)
    if not samples:
        raise ValueError("No annotated samples were found in the CVAT export.")

    rng = random.Random(args.seed)
    rng.shuffle(samples)
    splits = split_items(samples, args.train_ratio, args.valid_ratio)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for split_name, split_samples in splits.items():
        write_coco_split(output_dir / split_name, split_samples, categories)

    write_data_yaml(output_dir, labels)

    summary_lines = [
        f"selected_images: {len(samples)}",
        f"train: {len(splits['train'])}",
        f"valid: {len(splits['valid'])}",
        f"test: {len(splits['test'])}",
        "classes:",
    ]
    summary_lines.extend(f"  - {label}: {class_counter.get(label, 0)}" for label in labels)
    (output_dir / "summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

    print(f"Prepared RF-DETR dataset written to: {output_dir}")
    for split_name in ("train", "valid", "test"):
        print(f"{split_name}: {len(splits[split_name])} images")
    print("Class instances:")
    for label in labels:
        print(f"  {label}: {class_counter.get(label, 0)}")


if __name__ == "__main__":
    main()
