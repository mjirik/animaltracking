#!/usr/bin/env python3
"""Record short RTSP clips from configured cameras.

Examples:
    python devel/dataset_preparation/record_rtsp_clips.py
    python devel/dataset_preparation/record_rtsp_clips.py --duration 30
    python devel/dataset_preparation/record_rtsp_clips.py --cameras camera_1
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple


CAMERA_ENV_NAMES = {
    "camera_1": ("RTSP_CAM1", "CAMERA1_URL"),
    "camera_2": ("RTSP_CAM2", "CAMERA2_URL"),
}
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_env_file(env_file: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not env_file.exists():
        return env

    for line_number, raw_line in enumerate(env_file.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            print(f"Skipping invalid .env line {line_number}: missing '='", file=sys.stderr)
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def get_camera_urls(env: Dict[str, str]) -> Dict[str, str]:
    urls: Dict[str, str] = {}
    for camera_name, env_names in CAMERA_ENV_NAMES.items():
        value = next(
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record short timestamped RTSP clips.")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PROJECT_ROOT / ".env",
        help="Path to the .env file with RTSP camera URLs.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "devel/dataset_preparation/video_clips",
        help="Directory where camera subdirectories will be created.",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Clip duration in seconds. Default is 30.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Per-camera ffmpeg timeout in seconds. Default is 45.",
    )
    parser.add_argument(
        "--cameras",
        nargs="+",
        choices=sorted(CAMERA_ENV_NAMES),
        default=sorted(CAMERA_ENV_NAMES),
        help="Which cameras to record. Default is both cameras.",
    )
    return parser.parse_args()


def build_output_path(output_root: Path, camera_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / camera_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{timestamp}.mp4"


def ffmpeg_command(rtsp_url: str, output_file: Path, duration: int) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-t",
        str(duration),
        "-map",
        "0:v:0",
        "-an",
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        str(output_file),
    ]


def record_clip(rtsp_url: str, output_file: Path, duration: int, timeout: int) -> None:
    subprocess.run(
        ffmpeg_command(rtsp_url=rtsp_url, output_file=output_file, duration=duration),
        check=True,
        timeout=timeout,
    )


def main() -> int:
    args = parse_args()
    if args.duration <= 0:
        print("--duration must be greater than 0", file=sys.stderr)
        return 2
    if args.timeout <= 0:
        print("--timeout must be greater than 0", file=sys.stderr)
        return 2
    if args.timeout < args.duration:
        print("--timeout should be at least as large as --duration", file=sys.stderr)
        return 2

    env = load_env_file(args.env_file)
    camera_urls = get_camera_urls(env)
    selected_cameras = {camera_name: camera_urls[camera_name] for camera_name in args.cameras if camera_name in camera_urls}

    missing_cameras = [camera_name for camera_name in args.cameras if camera_name not in selected_cameras]
    if missing_cameras:
        expected_vars = ", ".join("/".join(env_names) for env_names in CAMERA_ENV_NAMES.values())
        print(
            f"Missing RTSP URL for: {', '.join(missing_cameras)}. Expected variables: {expected_vars}",
            file=sys.stderr,
        )
        return 2

    args.output_root.mkdir(parents=True, exist_ok=True)

    success = True
    for camera_name, rtsp_url in selected_cameras.items():
        output_file = build_output_path(args.output_root, camera_name)
        try:
            record_clip(
                rtsp_url=rtsp_url,
                output_file=output_file,
                duration=args.duration,
                timeout=args.timeout,
            )
            print(f"{camera_name}: saved {output_file}")
        except FileNotFoundError:
            print("ffmpeg is not installed or is not on PATH", file=sys.stderr)
            return 1
        except subprocess.TimeoutExpired:
            print(
                f"{camera_name}: recording timed out after {args.timeout} seconds",
                file=sys.stderr,
            )
            success = False
        except subprocess.CalledProcessError as exc:
            print(
                f"{camera_name}: ffmpeg failed with exit code {exc.returncode}",
                file=sys.stderr,
            )
            success = False

    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
