from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .env_config import CameraEnvConfig, PenEnvConfig, load_dotenv, parse_camera_configs
from .models import Pen, PenActivityQuarterHour, PenState


@dataclass(frozen=True)
class DashboardPenCard:
    key: str
    name: str
    camera_id: int
    pen_index: int
    display_order: int
    active_tracks: int
    today_distance_m: float
    yesterday_distance_m: float
    last_7_days_distance_m: float
    snapshot_url: str | None
    snapshot_updated_at: object | None
    last_caretaker_visit_at: object | None
    activity_last_24h: list[dict[str, object]]
    caretaker_presence_last_24h: list[dict[str, object]]


def serialize_dashboard_card(card: DashboardPenCard) -> dict[str, object]:
    payload = asdict(card)
    snapshot_updated_at = payload.get("snapshot_updated_at")
    if isinstance(snapshot_updated_at, datetime):
        payload["snapshot_updated_at"] = snapshot_updated_at.isoformat()
    return payload


def sync_pens_from_env() -> list[CameraEnvConfig]:
    env = load_dotenv()
    camera_configs = parse_camera_configs(env)
    active_keys: set[str] = set()

    with transaction.atomic():
        for camera in camera_configs:
            for pen_config in camera.pens:
                active_keys.add(pen_config.key)
                pen, _ = Pen.objects.update_or_create(
                    key=pen_config.key,
                    defaults={
                        "name": pen_config.name,
                        "camera_id": pen_config.camera_id,
                        "pen_index": pen_config.pen_index,
                        "roi_xyxy_norm_in_camroi": list(pen_config.roi_xyxy_norm_in_camroi),
                        "image_height_m": pen_config.image_height_m,
                        "is_active": True,
                    },
                )
                PenState.objects.get_or_create(pen=pen)

        if active_keys:
            Pen.objects.exclude(key__in=active_keys).update(is_active=False)

    return camera_configs


def media_url_for_relative_path(relative_path: str | None) -> str | None:
    if not relative_path:
        return None
    return f"{settings.MEDIA_URL}{relative_path.lstrip('/')}"


def snapshot_url_for(state: PenState) -> str | None:
    return media_url_for_relative_path(state.snapshot_relative_path)


def floor_to_quarter_hour(timestamp: datetime) -> datetime:
    return timestamp.replace(minute=(timestamp.minute // 15) * 15, second=0, microsecond=0)


def build_activity_last_24h(pen: Pen) -> list[dict[str, object]]:
    now = timezone.localtime()
    current_window = floor_to_quarter_hour(now)
    window_starts = [current_window - timedelta(minutes=15 * offset) for offset in range(95, -1, -1)]
    activities = {
        activity.window_start: activity
        for activity in PenActivityQuarterHour.objects.filter(
            pen=pen,
            label="pig",
            window_start__gte=window_starts[0],
            window_start__lte=window_starts[-1],
        )
    }

    result: list[dict[str, object]] = []
    for window_start in window_starts:
        local_window_start = timezone.localtime(window_start)
        show_label = local_window_start.minute == 0 and local_window_start.hour % 3 == 0
        activity = activities.get(window_start)
        result.append(
            {
                "window_start": window_start.isoformat(),
                "short_label": local_window_start.strftime("%H:%M"),
                "display_label": local_window_start.strftime("%H") if show_label else "",
                "distance_total_m": float(activity.distance_total_m) if activity else 0.0,
                "present": bool(activity.present) if activity else False,
                "snapshot_url": media_url_for_relative_path(activity.snapshot_relative_path) if activity else None,
                "snapshot_captured_at": activity.snapshot_captured_at.isoformat()
                if activity and activity.snapshot_captured_at
                else None,
            }
        )
    return result


def build_caretaker_presence_last_24h(pen: Pen) -> list[dict[str, object]]:
    now = timezone.localtime()
    current_window = floor_to_quarter_hour(now)
    window_starts = [current_window - timedelta(minutes=15 * offset) for offset in range(95, -1, -1)]
    activities = {
        activity.window_start: activity
        for activity in PenActivityQuarterHour.objects.filter(
            pen=pen,
            label="caretaker",
            window_start__gte=window_starts[0],
            window_start__lte=window_starts[-1],
        )
    }

    result: list[dict[str, object]] = []
    for window_start in window_starts:
        local_window_start = timezone.localtime(window_start)
        activity = activities.get(window_start)
        result.append(
            {
                "window_start": window_start.isoformat(),
                "short_label": local_window_start.strftime("%H:%M"),
                "present": bool(activity.present) if activity else False,
            }
        )
    return result


def build_dashboard_cards() -> list[DashboardPenCard]:
    env = load_dotenv()
    camera_configs = parse_camera_configs(env)
    display_order_by_key = {
        pen_config.key: pen_config.display_order
        for camera_config in camera_configs
        for pen_config in camera_config.pens
    }
    pens = Pen.objects.filter(is_active=True).select_related("state").order_by("camera_id", "pen_index")
    latest_caretaker_visit_by_pen_id: dict[int, object] = {}
    caretaker_activities = PenActivityQuarterHour.objects.filter(
        pen__in=pens,
        label="caretaker",
        last_seen_at__isnull=False,
    ).order_by("pen_id", "-last_seen_at")
    for activity in caretaker_activities:
        latest_caretaker_visit_by_pen_id.setdefault(activity.pen_id, activity.last_seen_at)

    cards: list[DashboardPenCard] = []
    for pen in pens:
        state = getattr(pen, "state", None)
        detections = state.detections_json if state and isinstance(state.detections_json, list) else []
        active_track_ids = {
            detection.get("tracker_id")
            for detection in detections
            if detection.get("tracker_id") is not None
        }
        cards.append(
            DashboardPenCard(
                key=pen.key,
                name=pen.name,
                camera_id=pen.camera_id,
                pen_index=pen.pen_index,
                display_order=display_order_by_key.get(pen.key, pen.camera_id * 100 + pen.pen_index),
                active_tracks=len(active_track_ids),
                today_distance_m=state.today_distance_m if state else 0.0,
                yesterday_distance_m=state.yesterday_distance_m if state else 0.0,
                last_7_days_distance_m=state.last_7_days_distance_m if state else 0.0,
                snapshot_url=snapshot_url_for(state) if state else None,
                snapshot_updated_at=state.snapshot_updated_at if state else None,
                last_caretaker_visit_at=latest_caretaker_visit_by_pen_id.get(pen.id),
                activity_last_24h=build_activity_last_24h(pen),
                caretaker_presence_last_24h=build_caretaker_presence_last_24h(pen),
            )
        )
    return sorted(cards, key=lambda card: (card.display_order, card.camera_id, card.pen_index))
