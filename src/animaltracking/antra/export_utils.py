from __future__ import annotations

import csv
from datetime import datetime

from django.http import HttpResponse

from .models import PenActivityQuarterHour


EXPORT_FIELDNAMES = [
    "pen_key",
    "pen_name",
    "camera_id",
    "pen_index",
    "label",
    "window_start",
    "window_end",
    "present",
    "presence_seconds",
    "sample_count",
    "concurrent_count_mode",
    "concurrent_count_mean",
    "concurrent_count_max",
    "distance_total_m",
    "distance_mean_per_track_m",
    "distance_variance_per_track_m",
    "track_count",
    "detection_count",
    "first_seen_at",
    "last_seen_at",
    "snapshot_relative_path",
    "snapshot_captured_at",
]


def activity_export_queryset():
    return PenActivityQuarterHour.objects.select_related("pen").order_by(
        "pen__camera_id",
        "pen__pen_index",
        "label",
        "window_start",
    )


def iter_activity_export_rows(queryset):
    for activity in queryset:
        yield [
            activity.pen.key,
            activity.pen.name,
            activity.pen.camera_id,
            activity.pen.pen_index,
            activity.label,
            activity.window_start.isoformat(),
            activity.window_end.isoformat(),
            activity.present,
            activity.presence_seconds,
            activity.sample_count,
            activity.concurrent_count_mode,
            activity.concurrent_count_mean,
            activity.concurrent_count_max,
            activity.distance_total_m,
            activity.distance_mean_per_track_m,
            activity.distance_variance_per_track_m,
            activity.track_count,
            activity.detection_count,
            activity.first_seen_at.isoformat() if activity.first_seen_at else "",
            activity.last_seen_at.isoformat() if activity.last_seen_at else "",
            activity.snapshot_relative_path,
            activity.snapshot_captured_at.isoformat() if activity.snapshot_captured_at else "",
        ]


def build_activity_csv_response(queryset=None, filename: str | None = None) -> HttpResponse:
    response = HttpResponse(content_type="text/csv")
    export_filename = filename or f"pen_activity_quarter_hour_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{export_filename}"'
    writer = csv.writer(response)
    writer.writerow(EXPORT_FIELDNAMES)
    for row in iter_activity_export_rows(queryset or activity_export_queryset()):
        writer.writerow(row)
    return response
