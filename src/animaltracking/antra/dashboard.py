from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction

from .env_config import CameraEnvConfig, PenEnvConfig, load_dotenv, parse_camera_configs
from .models import Pen, PenState


@dataclass(frozen=True)
class DashboardPenCard:
    key: str
    name: str
    camera_id: int
    pen_index: int
    today_distance_m: float
    yesterday_distance_m: float
    last_7_days_distance_m: float
    snapshot_url: str | None
    snapshot_updated_at: object | None


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
                        "is_active": True,
                    },
                )
                PenState.objects.get_or_create(pen=pen)

        if active_keys:
            Pen.objects.exclude(key__in=active_keys).update(is_active=False)

    return camera_configs


def snapshot_url_for(state: PenState) -> str | None:
    if not state.snapshot_relative_path:
        return None
    relative_path = state.snapshot_relative_path.lstrip("/")
    return f"{settings.MEDIA_URL}{relative_path}"


def build_dashboard_cards() -> list[DashboardPenCard]:
    sync_pens_from_env()
    pens = Pen.objects.filter(is_active=True).select_related("state").order_by("camera_id", "pen_index")
    cards: list[DashboardPenCard] = []
    for pen in pens:
        state = getattr(pen, "state", None)
        cards.append(
            DashboardPenCard(
                key=pen.key,
                name=pen.name,
                camera_id=pen.camera_id,
                pen_index=pen.pen_index,
                today_distance_m=state.today_distance_m if state else 0.0,
                yesterday_distance_m=state.yesterday_distance_m if state else 0.0,
                last_7_days_distance_m=state.last_7_days_distance_m if state else 0.0,
                snapshot_url=snapshot_url_for(state) if state else None,
                snapshot_updated_at=state.snapshot_updated_at if state else None,
            )
        )
    return cards
