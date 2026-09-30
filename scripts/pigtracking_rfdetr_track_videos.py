from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import supervision as sv
from PIL import Image
from trackers import ByteTrackTracker


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src" / "animaltracking"))

from antra.rfdetr_runtime import (  # noqa: E402
    build_model,
    class_name_for_id,
    default_device,
    detection_rows,
    draw_predictions,
    load_class_map,
)


SUPPORTED_VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".m4v"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RF-DETR + ByteTrack over pigtracking videos.")
    parser.add_argument(
        "--model",
        type=Path,
        default=Path("models") / "pigtracking_rfdetr_best.pth",
        help="Path to a trained RF-DETR checkpoint.",
    )
    parser.add_argument(
        "--model-size",
        choices=["nano", "small", "base", "medium", "large"],
        help="RF-DETR model size used by the checkpoint. If omitted, metadata is used.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("devel") / "dataset_preparation" / "video_clips",
        help="Input video file or directory.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. If omitted, a timestamped directory is created in runs/track_video.",
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
    parser.add_argument("--lost-track-buffer", type=int, default=30)
    parser.add_argument("--minimum-consecutive-frames", type=int, default=1)
    parser.add_argument("--minimum-iou-threshold", type=float, default=0.3)
    parser.add_argument("--track-activation-threshold", type=float, default=0.25)
    parser.add_argument("--high-conf-det-threshold", type=float, default=0.25)
    parser.add_argument("--history-length", type=int, default=10)
    parser.add_argument("--smoothing-alpha", type=float, default=0.35)
    return parser.parse_args()


def resolve_output_dir(output: Path | None) -> Path:
    if output is not None:
        return output.resolve()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return (Path("runs") / "track_video" / f"rfdetr_pigtracking_{timestamp}").resolve()


def video_paths(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES else []
    if not input_path.exists():
        return []
    candidates = input_path.rglob("*")
    return sorted(
        path for path in candidates if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_SUFFIXES
    )


def iou_xyxy(box_a: np.ndarray, box_b: np.ndarray) -> float:
    ax1, ay1, ax2, ay2 = [float(value) for value in box_a]
    bx1, by1, bx2, by2 = [float(value) for value in box_b]
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter_area = inter_w * inter_h
    if inter_area <= 0.0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union_area = area_a + area_b - inter_area
    if union_area <= 0.0:
        return 0.0
    return inter_area / union_area


def to_supervision_detections(detections: Any) -> sv.Detections:
    xyxy = np.asarray(getattr(detections, "xyxy", []), dtype=np.float32)
    if xyxy.size == 0:
        return sv.Detections.empty()
    confidence = getattr(detections, "confidence", None)
    class_id = getattr(detections, "class_id", None)
    return sv.Detections(
        xyxy=xyxy,
        confidence=np.asarray(confidence, dtype=np.float32) if confidence is not None else None,
        class_id=np.asarray(class_id, dtype=int) if class_id is not None else None,
    )


def restore_detection_metadata(
    tracked_detections: sv.Detections,
    original_detections: sv.Detections,
) -> sv.Detections:
    if len(tracked_detections) == 0 or len(original_detections) == 0:
        return tracked_detections

    restored_class_ids: list[int] = []
    restored_confidences: list[float] = []
    for tracked_box in tracked_detections.xyxy:
        best_index = 0
        best_iou = -1.0
        for index, original_box in enumerate(original_detections.xyxy):
            overlap = iou_xyxy(tracked_box, original_box)
            if overlap > best_iou:
                best_iou = overlap
                best_index = index

        if original_detections.class_id is not None:
            restored_class_ids.append(int(original_detections.class_id[best_index]))
        if original_detections.confidence is not None:
            restored_confidences.append(float(original_detections.confidence[best_index]))

    if restored_class_ids:
        tracked_detections.class_id = np.asarray(restored_class_ids, dtype=int)
    if restored_confidences:
        tracked_detections.confidence = np.asarray(restored_confidences, dtype=np.float32)
    return tracked_detections


def add_trajectory_points(
    rows: list[dict[str, Any]],
    tracking_state: dict[str, dict[str, Any]],
    history_length: int,
    smoothing_alpha: float,
) -> None:
    current_state: dict[str, dict[str, Any]] = {}
    for row in rows:
        tracker_id = row.get("tracker_id")
        if tracker_id is None:
            continue
        tracker_key = str(tracker_id)
        x1, y1, x2, y2 = row["bbox_xyxy"]
        center_x = (float(x1) + float(x2)) / 2.0
        center_y = (float(y1) + float(y2)) / 2.0
        previous = tracking_state.get(tracker_key, {})
        previous_history = previous.get("history", [])
        previous_smooth_x = float(previous.get("smooth_center_x", center_x))
        previous_smooth_y = float(previous.get("smooth_center_y", center_y))
        smooth_center_x = center_x if not previous else (
            smoothing_alpha * center_x + (1.0 - smoothing_alpha) * previous_smooth_x
        )
        smooth_center_y = center_y if not previous else (
            smoothing_alpha * center_y + (1.0 - smoothing_alpha) * previous_smooth_y
        )
        history = [list(point) for point in previous_history]
        history.append([smooth_center_x, smooth_center_y])
        history = history[-history_length:]
        current_state[tracker_key] = {
            "smooth_center_x": smooth_center_x,
            "smooth_center_y": smooth_center_y,
            "history": history,
        }
        row["trajectory_points"] = history
    tracking_state.clear()
    tracking_state.update(current_state)


def process_video(
    video_path: Path,
    input_root: Path,
    output_dir: Path,
    model: Any,
    class_map: dict[int, str],
    args: argparse.Namespace,
) -> dict[str, Any]:
    relative_path = video_path.relative_to(input_root) if input_root.is_dir() else Path(video_path.name)
    output_video_path = output_dir / relative_path.parent / f"{video_path.stem}_tracked.mp4"
    output_json_path = output_dir / relative_path.parent / f"{video_path.stem}_tracks.json"
    output_video_path.parent.mkdir(parents=True, exist_ok=True)

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"Unable to open video: {video_path}")

    fps = capture.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0:
        fps = 25.0
    frame_width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if frame_width <= 0 or frame_height <= 0:
        raise RuntimeError(f"Invalid video geometry for {video_path}")

    tracker = ByteTrackTracker(
        frame_rate=max(1.0, fps),
        lost_track_buffer=args.lost_track_buffer,
        track_activation_threshold=min(args.track_activation_threshold, args.threshold),
        high_conf_det_threshold=min(args.high_conf_det_threshold, args.threshold),
        minimum_consecutive_frames=args.minimum_consecutive_frames,
        minimum_iou_threshold=args.minimum_iou_threshold,
    )
    tracking_state: dict[str, dict[str, Any]] = {}

    writer = cv2.VideoWriter(
        str(output_video_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (frame_width, frame_height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"Unable to create output video: {output_video_path}")

    frame_index = 0
    class_counter: Counter[str] = Counter()
    tracked_ids: set[int] = set()
    frame_summaries: list[dict[str, Any]] = []

    try:
        while True:
            ok, frame_bgr = capture.read()
            if not ok:
                break

            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame_rgb)
            detections = model.predict(image)
            original_sv = to_supervision_detections(detections)
            tracked = tracker.update(original_sv)
            tracked = restore_detection_metadata(tracked, original_sv)
            rows = detection_rows(tracked, args.threshold)

            for row in rows:
                row["class_name"] = class_name_for_id(row["class_id"], class_map)
            add_trajectory_points(rows, tracking_state, args.history_length, args.smoothing_alpha)

            annotated = draw_predictions(image, rows, class_map)
            writer.write(cv2.cvtColor(np.asarray(annotated), cv2.COLOR_RGB2BGR))

            frame_rows: list[dict[str, Any]] = []
            for row in rows:
                class_name = row.get("class_name") or "object"
                class_counter[str(class_name)] += 1
                tracker_id = row.get("tracker_id")
                if tracker_id is not None:
                    tracked_ids.add(int(tracker_id))
                frame_rows.append(
                    {
                        "bbox_xyxy": [round(float(value), 2) for value in row["bbox_xyxy"]],
                        "confidence": None if row["confidence"] is None else round(float(row["confidence"]), 4),
                        "class_id": row["class_id"],
                        "class_name": class_name,
                        "tracker_id": tracker_id,
                    }
                )

            frame_summaries.append(
                {
                    "frame_index": frame_index,
                    "timestamp_seconds": round(frame_index / fps, 3),
                    "detections": frame_rows,
                }
            )
            frame_index += 1
    finally:
        capture.release()
        writer.release()

    summary = {
        "video": str(video_path.resolve()),
        "output_video": str(output_video_path.resolve()),
        "frame_count": frame_index,
        "fps": fps,
        "width": frame_width,
        "height": frame_height,
        "tracked_ids": sorted(tracked_ids),
        "class_counts": dict(sorted(class_counter.items())),
        "frames": frame_summaries,
    }
    output_json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    summary["output_json"] = str(output_json_path.resolve())
    return summary


def main() -> None:
    args = parse_args()
    model_path = args.model.resolve()
    input_path = args.input.resolve()
    output_dir = resolve_output_dir(args.output)
    class_map = load_class_map(args.class_map.resolve())
    num_classes = max(class_map) if class_map else None

    if not model_path.exists():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")

    videos = video_paths(input_path)
    if not videos:
        raise ValueError(f"No supported videos found in {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    model = build_model(args.model_size, model_path, args.device, num_classes)

    summaries = [
        process_video(video_path, input_path, output_dir, model, class_map, args)
        for video_path in videos
    ]
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")

    print(f"Tracked videos saved to: {output_dir}")
    print(f"Run summary: {summary_path}")


if __name__ == "__main__":
    main()
