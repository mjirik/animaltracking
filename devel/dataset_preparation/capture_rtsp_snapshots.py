#!/usr/bin/env python3
"""Capture timestamped images from two RTSP cameras for CVAT annotation.

Example:
    python devel/dataset_preparation/capture_rtsp_snapshots.py --once
    python devel/dataset_preparation/capture_rtsp_snapshots.py --interval 600

The script reads camera URLs from .env. Supported variable names are:
    RTSP_CAM1, RTSP_CAM2
    CAMERA1_URL, CAMERA2_URL
Optional ROI variables:
    RTSP_CAM1_ROI_XYXY_NORM, RTSP_CAM2_ROI_XYXY_NORM
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


CAMERA_ENV_NAMES = {  # type: Dict[str, Tuple[str, ...]]
    "camera_1": ("RTSP_CAM1", "CAMERA1_URL"),
    "camera_2": ("RTSP_CAM2", "CAMERA2_URL"),
}
CAMERA_ROI_ENV_NAMES = {  # type: Dict[str, Tuple[str, ...]]
    "camera_1": ("RTSP_CAM1_ROI_XYXY_NORM", "CAMERA1_ROI_XYXY_NORM"),
    "camera_2": ("RTSP_CAM2_ROI_XYXY_NORM", "CAMERA2_ROI_XYXY_NORM"),
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(env_file: Path) -> Dict[str, str]:
    """Load a simple KEY=VALUE .env file without extra dependencies."""
    env = {}  # type: Dict[str, str]
    if not env_file.exists():
        return env

    for line_number, raw_line in enumerate(env_file.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            print(
                f"Skipping invalid .env line {line_number}: missing '='",
                file=sys.stderr,
            )
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def get_camera_urls(env: Dict[str, str]) -> Dict[str, str]:
    urls = {}  # type: Dict[str, str]
    for camera_name, env_names in CAMERA_ENV_NAMES.items():
        value = next(  # type: Optional[str]
            (
                env.get(env_name) or os.environ.get(env_name)
                for env_name in env_names
                if env.get(env_name) or os.environ.get(env_name)
            ),
            None,
        )
        if value:
            urls[camera_name] = value
    return urls


def parse_roi_value(raw_value: str, camera_name: str) -> Tuple[float, float, float, float]:
    parts = [part.strip() for part in raw_value.split(",")]
    if len(parts) != 4:
        raise ValueError(
            "{} ROI must have 4 comma-separated values in x_min,y_min,x_max,y_max format".format(
                camera_name
            )
        )

    try:
        x_min, y_min, x_max, y_max = [float(part) for part in parts]
    except ValueError:
        raise ValueError("{} ROI must contain only numeric values".format(camera_name))

    for value_name, value in (
        ("x_min", x_min),
        ("y_min", y_min),
        ("x_max", x_max),
        ("y_max", y_max),
    ):
        if not 0 <= value <= 1:
            raise ValueError(
                "{} ROI {} must be in the 0..1 range".format(camera_name, value_name)
            )

    if x_min >= x_max:
        raise ValueError("{} ROI must satisfy x_min < x_max".format(camera_name))
    if y_min >= y_max:
        raise ValueError("{} ROI must satisfy y_min < y_max".format(camera_name))

    return x_min, y_min, x_max, y_max


def get_camera_rois(env: Dict[str, str]) -> Dict[str, Tuple[float, float, float, float]]:
    rois = {}  # type: Dict[str, Tuple[float, float, float, float]]
    for camera_name, env_names in CAMERA_ROI_ENV_NAMES.items():
        raw_value = next(  # type: Optional[str]
            (
                env.get(env_name) or os.environ.get(env_name)
                for env_name in env_names
                if env.get(env_name) or os.environ.get(env_name)
            ),
            None,
        )
        if raw_value:
            rois[camera_name] = parse_roi_value(raw_value, camera_name)
        else:
            rois[camera_name] = (0.0, 0.0, 1.0, 1.0)
    return rois


def safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def capture_snapshot(
    rtsp_url: str,
    output_file: Path,
    timeout: int,
    roi: Tuple[float, float, float, float],
) -> Path:
    x_min, y_min, x_max, y_max = roi
    crop_filter = (
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
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-vf",
        crop_filter,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-y",
        str(output_file),
    ]

    subprocess.run(command, check=True, timeout=timeout)
    return output_file


def get_image_signature(image_file: Path, compare_width: int, timeout: int) -> bytes:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(image_file),
        "-vf",
        f"scale={compare_width}:-1,format=gray",
        "-f",
        "rawvideo",
        "-",
    ]

    completed = subprocess.run(
        command,
        check=True,
        stdout=subprocess.PIPE,
        timeout=timeout,
    )
    return completed.stdout


def get_change_ratio(
    previous_signature: bytes,
    current_signature: bytes,
    pixel_threshold: float,
) -> float:
    if not previous_signature or not current_signature:
        return 1.0
    if len(previous_signature) != len(current_signature):
        return 1.0

    threshold = pixel_threshold * 255
    changed_pixels = sum(
        1
        for previous_value, current_value in zip(previous_signature, current_signature)
        if abs(previous_value - current_value) > threshold
    )
    return changed_pixels / len(current_signature)


def capture_all_cameras(
    camera_urls: Dict[str, str],
    camera_rois: Dict[str, Tuple[float, float, float, float]],
    output_root: Path,
    timeout: int,
    compare_width: int,
    pixel_threshold: float,
    image_threshold: float,
    last_saved_signatures: Dict[str, bytes],
    save_all: bool,
) -> bool:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success = True

    for camera_name, rtsp_url in camera_urls.items():
        output_dir = output_root / camera_name
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{timestamp}.jpg"

        with tempfile.NamedTemporaryFile(
            prefix=f"{camera_name}_",
            suffix=".jpg",
            dir=str(output_dir),
            delete=False,
        ) as temp_file:
            temp_file_path = Path(temp_file.name)

        try:
            capture_snapshot(
                rtsp_url=rtsp_url,
                output_file=temp_file_path,
                timeout=timeout,
                roi=camera_rois[camera_name],
            )
            current_signature = get_image_signature(
                image_file=temp_file_path,
                compare_width=compare_width,
                timeout=timeout,
            )

            if save_all or camera_name not in last_saved_signatures:
                change_ratio = 1.0
                should_save = True
            else:
                change_ratio = get_change_ratio(
                    previous_signature=last_saved_signatures[camera_name],
                    current_signature=current_signature,
                    pixel_threshold=pixel_threshold,
                )
                should_save = change_ratio > image_threshold

            if should_save:
                temp_file_path.replace(output_file)
                last_saved_signatures[camera_name] = current_signature
                print(
                    f"{camera_name}: saved {output_file} "
                    f"(change_ratio={change_ratio:.4f})"
                )
            else:
                safe_unlink(temp_file_path)
                print(
                    f"{camera_name}: skipped "
                    f"(change_ratio={change_ratio:.4f})"
                )
        except FileNotFoundError:
            safe_unlink(temp_file_path)
            print("ffmpeg is not installed or is not on PATH", file=sys.stderr)
            return False
        except subprocess.TimeoutExpired:
            safe_unlink(temp_file_path)
            print(
                f"{camera_name}: capture timed out after {timeout} seconds",
                file=sys.stderr,
            )
            success = False
        except subprocess.CalledProcessError as exc:
            safe_unlink(temp_file_path)
            print(
                f"{camera_name}: ffmpeg failed with exit code {exc.returncode}",
                file=sys.stderr,
            )
            success = False

    return success


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save timestamped JPEG snapshots from RTSP cameras.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="Path to the .env file with RTSP_CAM1/RTSP_CAM2 URLs.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "devel/dataset_preparation/snapshots",
        help="Directory where camera_1 and camera_2 folders will be created.",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Capture interval in seconds. Default is 600 seconds.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout for one camera capture in seconds.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Capture one snapshot from each camera and exit.",
    )
    parser.add_argument(
        "--compare-width",
        type=int,
        default=320,
        help="Width for grayscale image comparison. Default is 320 px.",
    )
    parser.add_argument(
        "--pixel-threshold",
        type=float,
        default=20 / 255,
        help=(
            "Per-pixel brightness change threshold in the 0..1 range. "
            "Default is 20/255."
        ),
    )
    parser.add_argument(
        "--image-threshold",
        type=float,
        default=0.02,
        help=(
            "Fraction of changed pixels needed to save an image, in the 0..1 "
            "range. Default is 0.02."
        ),
    )
    parser.add_argument(
        "--save-all",
        action="store_true",
        help="Save every captured image without change filtering.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 0 <= args.pixel_threshold <= 1:
        print("--pixel-threshold must be in the 0..1 range", file=sys.stderr)
        return 2
    if not 0 <= args.image_threshold <= 1:
        print("--image-threshold must be in the 0..1 range", file=sys.stderr)
        return 2
    if args.compare_width <= 0:
        print("--compare-width must be greater than 0", file=sys.stderr)
        return 2

    env = load_env_file(args.env_file)
    camera_urls = get_camera_urls(env)
    try:
        camera_rois = get_camera_rois(env)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    missing_cameras = sorted(set(CAMERA_ENV_NAMES) - set(camera_urls))
    if missing_cameras:
        expected_vars = ", ".join(
            "/".join(env_names) for env_names in CAMERA_ENV_NAMES.values()
        )
        print(
            f"Missing RTSP URL for: {', '.join(missing_cameras)}. "
            f"Expected variables: {expected_vars}",
            file=sys.stderr,
        )
        return 2

    args.output_root.mkdir(parents=True, exist_ok=True)
    last_saved_signatures = {}  # type: Dict[str, bytes]

    while True:
        started_at = time.monotonic()
        success = capture_all_cameras(
            camera_urls=camera_urls,
            camera_rois=camera_rois,
            output_root=args.output_root,
            timeout=args.timeout,
            compare_width=args.compare_width,
            pixel_threshold=args.pixel_threshold,
            image_threshold=args.image_threshold,
            last_saved_signatures=last_saved_signatures,
            save_all=args.save_all,
        )
        if args.once:
            return 0 if success else 1

        elapsed = time.monotonic() - started_at
        sleep_for = max(0, args.interval - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
