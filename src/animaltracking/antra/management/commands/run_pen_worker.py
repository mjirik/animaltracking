from __future__ import annotations

import io
import math
import time
import subprocess
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image
import numpy as np
import supervision as sv
from trackers import ByteTrackTracker

from antra.dashboard import sync_pens_from_env
from antra.env_config import CameraEnvConfig, PenEnvConfig
from antra.models import PenActivityQuarterHour, PenState
from antra.rfdetr_runtime import (
    build_model,
    class_name_for_id,
    default_device,
    detection_rows,
    draw_predictions,
    load_class_map,
)


def crop_box(size: tuple[int, int], roi: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = size
    x1, y1, x2, y2 = roi
    left = max(0, min(width - 1, round(x1 * width)))
    top = max(0, min(height - 1, round(y1 * height)))
    right = max(left + 1, min(width, round(x2 * width)))
    bottom = max(top + 1, min(height, round(y2 * height)))
    return left, top, right, bottom


def ffmpeg_crop_filter(roi: tuple[float, float, float, float] | None) -> str | None:
    if roi is None:
        return None
    x_min, y_min, x_max, y_max = roi
    return (
        "crop="
        "in_w*{width}:"
        "in_h*{height}:"
        "in_w*{x_offset}:"
        "in_h*{y_offset}".format(
            width=x_max - x_min,
            height=y_max - y_min,
            x_offset=x_min,
            y_offset=y_min,
        )
    )


def capture_camera_frame(
    rtsp_url: str,
    timeout: int,
    camera_roi: tuple[float, float, float, float] | None,
) -> Image.Image:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
    ]
    crop_filter = ffmpeg_crop_filter(camera_roi)
    if crop_filter is not None:
        command.extend(["-vf", crop_filter])
    command.extend(
        [
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ]
    )

    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        timeout=timeout,
    )
    with Image.open(io.BytesIO(completed.stdout)) as image:
        return image.convert("RGB")


def pen_image_for_camera_frame(
    camera_frame: Image.Image,
    pen_config: PenEnvConfig,
) -> tuple[Image.Image, str, timezone.datetime]:
    pen_image = camera_frame.crop(crop_box(camera_frame.size, pen_config.roi_xyxy_norm_in_camroi))
    captured_at = timezone.now()
    relative_path = str(Path("pens") / pen_config.key / "latest.jpg")
    return pen_image, relative_path, captured_at


def center_of_bbox(row: dict[str, object]) -> tuple[float, float]:
    x1, y1, x2, y2 = row["bbox_xyxy"]
    return (float(x1 + x2) / 2.0, float(y1 + y2) / 2.0)


def normalize_daily_distance_json(values: dict | None) -> dict[str, float]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, value in values.items():
        try:
            normalized[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


def normalize_tracking_state_json(values: dict | None) -> dict[str, dict[str, object]]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, dict[str, object]] = {}
    for tracker_key, payload in values.items():
        if not isinstance(payload, dict):
            continue
        history = payload.get("history")
        normalized_history: list[list[float]] = []
        if isinstance(history, list):
            for point in history:
                if not isinstance(point, (list, tuple)) or len(point) != 2:
                    continue
                try:
                    normalized_history.append([float(point[0]), float(point[1])])
                except (TypeError, ValueError):
                    continue
        normalized[str(tracker_key)] = {
            "center_x": float(payload.get("center_x", normalized_history[-1][0] if normalized_history else 0.0)),
            "center_y": float(payload.get("center_y", normalized_history[-1][1] if normalized_history else 0.0)),
            "observed_at": payload.get("observed_at"),
            "history": normalized_history,
        }
    return normalized


def floor_to_quarter_hour(timestamp):
    minute = (timestamp.minute // 15) * 15
    return timestamp.replace(minute=minute, second=0, microsecond=0)


def normalize_track_distance_json(values: dict | None) -> dict[str, float]:
    if not isinstance(values, dict):
        return {}
    normalized: dict[str, float] = {}
    for key, value in values.items():
        try:
            normalized[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


def normalize_seen_track_ids_json(values) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values}


def iou_xyxy(box_a: np.ndarray, box_b: np.ndarray) -> float:
    x1 = max(float(box_a[0]), float(box_b[0]))
    y1 = max(float(box_a[1]), float(box_b[1]))
    x2 = min(float(box_a[2]), float(box_b[2]))
    y2 = min(float(box_a[3]), float(box_b[3]))
    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    area_a = max(0.0, float(box_a[2] - box_a[0])) * max(0.0, float(box_a[3] - box_a[1]))
    area_b = max(0.0, float(box_b[2] - box_b[0])) * max(0.0, float(box_b[3] - box_b[1]))
    union = area_a + area_b - intersection
    if union <= 0:
        return 0.0
    return intersection / union


class Command(BaseCommand):
    help = "Capture RTSP frames, process per-pen images, and refresh the dashboard."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._model = None
        self._class_map: dict[int, str] | None = None
        self._trackers: dict[str, ByteTrackTracker] = {}

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=float, default=0.5, help="Polling interval in seconds.")
        parser.add_argument("--once", action="store_true", help="Run a single processing pass and exit.")
        parser.add_argument("--threshold", type=float, default=0.25, help="Detection confidence threshold.")
        parser.add_argument("--device", default=default_device(), help="Inference device, for example cpu or cuda:0.")
        parser.add_argument("--capture-timeout", type=int, default=30, help="RTSP frame capture timeout in seconds.")
        parser.add_argument("--lost-track-buffer", type=int, default=120, help="ByteTrack lost track buffer in frames.")
        parser.add_argument("--minimum-consecutive-frames", type=int, default=1, help="ByteTrack minimum consecutive frames before confirming a track.")
        parser.add_argument("--minimum-iou-threshold", type=float, default=0.02, help="ByteTrack minimum IoU threshold for associating detections with existing tracks.")
        parser.add_argument("--track-activation-threshold", type=float, default=0.12, help="ByteTrack activation threshold for maintaining and initializing tracks.")
        parser.add_argument("--high-conf-det-threshold", type=float, default=0.18, help="ByteTrack high-confidence detection threshold used in the first association stage.")

    def handle(self, *args, **options):
        interval = max(1.0, float(options["interval"]))
        run_once = bool(options["once"])
        threshold = float(options["threshold"])
        device = str(options["device"])
        capture_timeout = max(1, int(options["capture_timeout"]))
        lost_track_buffer = max(1, int(options["lost_track_buffer"]))
        minimum_consecutive_frames = max(1, int(options["minimum_consecutive_frames"]))
        minimum_iou_threshold = max(0.0, float(options["minimum_iou_threshold"]))
        track_activation_threshold = max(0.0, float(options["track_activation_threshold"]))
        high_conf_det_threshold = max(0.0, float(options["high_conf_det_threshold"]))

        while True:
            processed = self.process_once(
                threshold=threshold,
                device=device,
                capture_timeout=capture_timeout,
                lost_track_buffer=lost_track_buffer,
                minimum_consecutive_frames=minimum_consecutive_frames,
                minimum_iou_threshold=minimum_iou_threshold,
                track_activation_threshold=track_activation_threshold,
                high_conf_det_threshold=high_conf_det_threshold,
                interval_seconds=interval,
            )
            self.stdout.write(self.style.SUCCESS(f"Processed {processed} pens."))
            if run_once:
                break
            time.sleep(interval)

    def process_once(
        self,
        threshold: float,
        device: str,
        capture_timeout: int,
        lost_track_buffer: int,
        minimum_consecutive_frames: int,
        minimum_iou_threshold: float,
        track_activation_threshold: float,
        high_conf_det_threshold: float,
        interval_seconds: float,
    ) -> int:
        camera_configs = sync_pens_from_env()
        model, class_map = self.ensure_model(device=device)
        processed = 0
        for camera_config in camera_configs:
            if not camera_config.rtsp_url:
                self.stdout.write(
                    self.style.WARNING(
                        f"No RTSP URL configured for camera {camera_config.camera_id}."
                    )
                )
                continue
            try:
                camera_frame = capture_camera_frame(
                    rtsp_url=camera_config.rtsp_url,
                    timeout=capture_timeout,
                    camera_roi=camera_config.camera_roi_xyxy_norm,
                )
            except FileNotFoundError:
                raise RuntimeError("ffmpeg is not installed or is not on PATH.")
            except subprocess.TimeoutExpired:
                self.stdout.write(
                    self.style.WARNING(
                        f"Camera {camera_config.camera_id}: capture timed out after {capture_timeout} seconds."
                    )
                )
                continue
            except subprocess.CalledProcessError as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"Camera {camera_config.camera_id}: ffmpeg failed with exit code {exc.returncode}."
                    )
                )
                continue

            for pen_config in camera_config.pens:
                pen_image, relative_path, captured_at = pen_image_for_camera_frame(
                    camera_frame,
                    pen_config,
                )
                detections = model.predict(pen_image)
                tracked_detections = self.track_pen_detections(
                    pen_key=pen_config.key,
                    detections=detections,
                    threshold=threshold,
                    lost_track_buffer=lost_track_buffer,
                    minimum_consecutive_frames=minimum_consecutive_frames,
                    minimum_iou_threshold=minimum_iou_threshold,
                    track_activation_threshold=track_activation_threshold,
                    high_conf_det_threshold=high_conf_det_threshold,
                    interval_seconds=interval_seconds,
                )
                rows = detection_rows(tracked_detections, threshold)
                rows = [
                    {
                        **row,
                        "class_name": class_name_for_id(row["class_id"], class_map),
                    }
                    for row in rows
                ]
                pen_state = PenState.objects.select_related("pen").get(pen__key=pen_config.key)
                pen_state.snapshot_relative_path = relative_path
                pen_state.snapshot_updated_at = captured_at
                pen_state.detections_json = rows
                self.update_distance_metrics(
                    pen_state=pen_state,
                    rows=rows,
                    pen_image_height_px=pen_image.height,
                    captured_at=captured_at,
                )
                self.update_quarter_hour_activity(
                    pen_state=pen_state,
                    rows=rows,
                    captured_at=captured_at,
                    interval_seconds=interval_seconds,
                    pen_image_height_px=pen_image.height,
                )
                annotated = draw_predictions(pen_image, rows, class_map)
                output_path = Path(settings.MEDIA_ROOT) / relative_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
                annotated.save(output_path, format="JPEG", quality=90)
                pen_state.save(
                    update_fields=[
                        "snapshot_relative_path",
                        "snapshot_updated_at",
                        "detections_json",
                        "tracking_state_json",
                        "daily_distance_json",
                        "today_distance_m",
                        "yesterday_distance_m",
                        "last_7_days_distance_m",
                        "updated_at",
                    ]
                )
                processed += 1
        return processed

    def ensure_model(self, device: str):
        if self._class_map is None:
            self._class_map = load_class_map()
        if self._model is None:
            num_classes = max(self._class_map) if self._class_map else None
            self._model = build_model(device=device, num_classes=num_classes)
        return self._model, self._class_map

    def track_pen_detections(
        self,
        pen_key: str,
        detections,
        threshold: float,
        lost_track_buffer: int,
        minimum_consecutive_frames: int,
        minimum_iou_threshold: float,
        track_activation_threshold: float,
        high_conf_det_threshold: float,
        interval_seconds: float,
    ):
        tracker = self._trackers.get(pen_key)
        if tracker is None:
            tracker = ByteTrackTracker(
                frame_rate=max(1.0, 1.0 / max(interval_seconds, 1e-6)),
                lost_track_buffer=lost_track_buffer,
                track_activation_threshold=min(track_activation_threshold, threshold),
                high_conf_det_threshold=min(high_conf_det_threshold, threshold),
                minimum_consecutive_frames=minimum_consecutive_frames,
                minimum_iou_threshold=minimum_iou_threshold,
            )
            self._trackers[pen_key] = tracker

        sv_detections = self.to_supervision_detections(detections)
        tracked = tracker.update(sv_detections)
        return self.restore_detection_metadata(tracked, sv_detections)

    @staticmethod
    def to_supervision_detections(detections) -> sv.Detections:
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

    @staticmethod
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

    def update_distance_metrics(
        self,
        pen_state: PenState,
        rows: list[dict[str, object]],
        pen_image_height_px: int,
        captured_at,
    ) -> None:
        if pen_image_height_px <= 0:
            return

        meters_per_pixel = float(pen_state.pen.image_height_m) / float(pen_image_height_px)
        previous_tracking_state = normalize_tracking_state_json(pen_state.tracking_state_json)
        current_tracking_state: dict[str, dict[str, float | str]] = {}
        daily_distance = normalize_daily_distance_json(pen_state.daily_distance_json)
        today_key = captured_at.astimezone(timezone.get_current_timezone()).date().isoformat()

        for row in rows:
            tracker_id = row.get("tracker_id")
            if tracker_id is None:
                continue
            tracker_key = str(tracker_id)
            center_x, center_y = center_of_bbox(row)
            previous = previous_tracking_state.get(tracker_key)
            previous_history = previous.get("history", []) if isinstance(previous, dict) else []
            history = [list(point) for point in previous_history]
            history.append([center_x, center_y])
            history = history[-10:]
            current_tracking_state[tracker_key] = {
                "center_x": center_x,
                "center_y": center_y,
                "observed_at": captured_at.isoformat(),
                "history": history,
            }
            row["trajectory_points"] = history

            if not isinstance(previous, dict):
                continue

            try:
                previous_center_x = float(previous["center_x"])
                previous_center_y = float(previous["center_y"])
            except (KeyError, TypeError, ValueError):
                continue

            distance_px = math.hypot(center_x - previous_center_x, center_y - previous_center_y)
            distance_m = distance_px * meters_per_pixel
            daily_distance[today_key] = daily_distance.get(today_key, 0.0) + distance_m

        cutoff_date = captured_at.date() - timedelta(days=7)
        daily_distance = {
            key: value
            for key, value in daily_distance.items()
            if key >= cutoff_date.isoformat()
        }

        pen_state.tracking_state_json = current_tracking_state
        pen_state.daily_distance_json = daily_distance
        pen_state.today_distance_m = round(daily_distance.get(today_key, 0.0), 3)
        yesterday_key = (captured_at.date() - timedelta(days=1)).isoformat()
        pen_state.yesterday_distance_m = round(daily_distance.get(yesterday_key, 0.0), 3)
        last_7_days = 0.0
        for day_offset in range(7):
            day_key = (captured_at.date() - timedelta(days=day_offset)).isoformat()
            last_7_days += daily_distance.get(day_key, 0.0)
        pen_state.last_7_days_distance_m = round(last_7_days, 3)

    def update_quarter_hour_activity(
        self,
        pen_state: PenState,
        rows: list[dict[str, object]],
        captured_at,
        interval_seconds: float,
        pen_image_height_px: int,
    ) -> None:
        if pen_image_height_px <= 0:
            return
        window_start = floor_to_quarter_hour(captured_at)
        window_end = window_start + timedelta(minutes=15)
        meters_per_pixel = float(pen_state.pen.image_height_m) / float(pen_image_height_px)
        rows_by_label: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            label = row.get("class_name") or "object"
            rows_by_label.setdefault(str(label), []).append(row)

        for label, label_rows in rows_by_label.items():
            with transaction.atomic():
                activity, _ = PenActivityQuarterHour.objects.select_for_update().get_or_create(
                    pen=pen_state.pen,
                    label=label,
                    window_start=window_start,
                    defaults={
                        "window_end": window_end,
                    },
                )

                track_distance = normalize_track_distance_json(activity.track_distance_json)
                seen_track_ids = normalize_seen_track_ids_json(activity.seen_track_ids_json)

                detection_count_increment = len(label_rows)
                present_track_ids: set[str] = set()
                for row in label_rows:
                    tracker_id = row.get("tracker_id")
                    if tracker_id is not None:
                        tracker_key = str(tracker_id)
                        present_track_ids.add(tracker_key)
                        seen_track_ids.add(tracker_key)

                    trajectory_points = row.get("trajectory_points") or []
                    if len(trajectory_points) < 2 or tracker_id is None:
                        continue
                    start = trajectory_points[-2]
                    end = trajectory_points[-1]
                    distance_px = math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
                    if distance_px <= 0:
                        continue
                    distance_m = distance_px * meters_per_pixel
                    track_distance[tracker_key] = track_distance.get(tracker_key, 0.0) + distance_m

                per_track_distances = list(track_distance.values())
                total_distance = sum(per_track_distances)
                mean_distance = total_distance / len(per_track_distances) if per_track_distances else 0.0
                variance_distance = (
                    sum((value - mean_distance) ** 2 for value in per_track_distances) / len(per_track_distances)
                    if per_track_distances
                    else 0.0
                )

                activity.window_end = window_end
                activity.present = True
                activity.presence_seconds += float(interval_seconds)
                activity.first_seen_at = activity.first_seen_at or captured_at
                activity.last_seen_at = captured_at
                activity.detection_count += detection_count_increment
                activity.track_count = len(seen_track_ids)
                activity.distance_total_m = round(total_distance, 4)
                activity.distance_mean_per_track_m = round(mean_distance, 4)
                activity.distance_variance_per_track_m = round(variance_distance, 6)
                activity.track_distance_json = track_distance
                activity.seen_track_ids_json = sorted(seen_track_ids)
                activity.save()
