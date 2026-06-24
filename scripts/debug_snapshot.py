#!/usr/bin/env python3
"""Standalone debug tool: fetch raw recording-snapshot bytes from a UniFi
Protect NVR and save them to disk for visual/manual inspection.

Reuses UnifyProtectClient (custom_components/unify_nvr_camera_sensor/api.py)
directly so this exercises the exact same request path as the integration.

Requires only `uiprotect` installed (pip install uiprotect). Pillow is
optional - if present, mean pixel brightness is printed as a quick signal
for "is this frame actually grey/black".

Usage:
    python3 scripts/debug_snapshot.py --host 192.168.1.1 --username admin --password secret
    python3 scripts/debug_snapshot.py --host 192.168.1.1 --username admin --password secret \
        --camera <camera_id> --lookback-minutes 1 5 30
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "custom_components" / "unify_nvr_camera_sensor"))

from api import UnifyProtectClient  # noqa: E402

_LOGGER = logging.getLogger("debug_snapshot")

JPEG_MAGIC = b"\xff\xd8\xff"


def _describe_bytes(data: bytes | None) -> str:
    if not data:
        return "EMPTY/None"
    is_jpeg = data.startswith(JPEG_MAGIC)
    desc = f"{len(data)} bytes, jpeg_magic={'yes' if is_jpeg else 'no'}"
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(data)).convert("L")
        pixels = list(img.getdata())
        mean_brightness = sum(pixels) / len(pixels)
        desc += f", mean_brightness={mean_brightness:.1f}/255"
    except ImportError:
        pass
    except Exception as err:
        desc += f", image_decode_error={err}"
    return desc


async def run(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    client = UnifyProtectClient(args.host, args.username, args.password)
    try:
        await client.connect()

        cameras = await client.get_cameras()
        if not cameras:
            print("No cameras found on this NVR.")
            return

        camera_ids = args.camera or [c["id"] for c in cameras]
        names_by_id = {c["id"]: c["name"] for c in cameras}

        unknown = [cid for cid in camera_ids if cid not in names_by_id]
        if unknown:
            print(f"Warning: unknown camera id(s) not on NVR: {unknown}")

        print(f"Cameras: {[(c['id'], c['name']) for c in cameras]}")
        print(f"Checking camera(s): {camera_ids}")
        print(f"Lookback window(s) (minutes): {args.lookback_minutes}")
        print()

        for camera_id in camera_ids:
            camera_name = names_by_id.get(camera_id, camera_id)
            for lookback_minutes in args.lookback_minutes:
                lookback_seconds = lookback_minutes * 60
                data = await client.get_recording_snapshot_bytes(camera_id, lookback_seconds)

                suffix = "jpg" if data and data.startswith(JPEG_MAGIC) else "bin"
                out_file = out_dir / f"{camera_id}_{lookback_minutes}m.{suffix}"
                if data:
                    out_file.write_bytes(data)

                print(
                    f"[{camera_name} / {camera_id}] {lookback_minutes}m ago: "
                    f"{_describe_bytes(data)}"
                    + (f" -> saved {out_file}" if data else "")
                )
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="NVR IP address or hostname")
    parser.add_argument("--username", required=True, help="Local NVR user (not Ubiquiti cloud account)")
    parser.add_argument("--password", required=True)
    parser.add_argument(
        "--camera",
        action="append",
        default=None,
        help="Camera id to check (repeatable). Defaults to all cameras on the NVR.",
    )
    parser.add_argument(
        "--lookback-minutes",
        type=int,
        nargs="+",
        default=[1, 5, 10, 30],
        help="Lookback windows in minutes to check (default: 1 5 10 30)",
    )
    parser.add_argument(
        "--out-dir",
        default="./snapshot_debug",
        help="Directory to save snapshot files into (default: ./snapshot_debug)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    asyncio.run(run(args))


if __name__ == "__main__":
    main()
