#!/usr/bin/env python3
"""Capture timestamped images from two RTSP cameras for CVAT annotation.

Example:
    python devel/dataset_preparation/capture_rtsp_snapshots.py --once
    python devel/dataset_preparation/capture_rtsp_snapshots.py --interval 600

The script reads camera URLs from .env. Supported variable names are:
    RTSP_CAM1, RTSP_CAM2
    CAMERA1_URL, CAMERA2_URL
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


CAMERA_ENV_NAMES = {  # type: Dict[str, Tuple[str, ...]]
    "camera_1": ("RTSP_CAM1", "CAMERA1_URL"),
    "camera_2": ("RTSP_CAM2", "CAMERA2_URL"),
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


def capture_snapshot(
    camera_name: str,
    rtsp_url: str,
    output_root: Path,
    timestamp: str,
    timeout: int,
) -> Path:
    output_dir = output_root / camera_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{timestamp}.jpg"

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        "-y",
        str(output_file),
    ]

    subprocess.run(command, check=True, timeout=timeout)
    return output_file


def capture_all_cameras(
    camera_urls: Dict[str, str],
    output_root: Path,
    timeout: int,
) -> bool:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    success = True

    for camera_name, rtsp_url in camera_urls.items():
        try:
            output_file = capture_snapshot(
                camera_name=camera_name,
                rtsp_url=rtsp_url,
                output_root=output_root,
                timestamp=timestamp,
                timeout=timeout,
            )
            print(f"{camera_name}: saved {output_file}")
        except FileNotFoundError:
            print("ffmpeg is not installed or is not on PATH", file=sys.stderr)
            return False
        except subprocess.TimeoutExpired:
            print(
                f"{camera_name}: capture timed out after {timeout} seconds",
                file=sys.stderr,
            )
            success = False
        except subprocess.CalledProcessError as exc:
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
        default=Path("devel/dataset_preparation/snapshots"),
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env = load_env_file(args.env_file)
    camera_urls = get_camera_urls(env)

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

    while True:
        started_at = time.monotonic()
        success = capture_all_cameras(
            camera_urls=camera_urls,
            output_root=args.output_root,
            timeout=args.timeout,
        )
        if args.once:
            return 0 if success else 1

        elapsed = time.monotonic() - started_at
        sleep_for = max(0, args.interval - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
