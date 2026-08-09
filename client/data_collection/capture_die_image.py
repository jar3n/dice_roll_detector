#!/usr/bin/env python3
"""
capture_die_image.py

Capture a single still image from the Raspberry Pi camera and save it with a
filename that encodes the die orientation, tray position, and die side facing up.
Designed to match the "Dice Roll Classifier — Data Collection Tracker" spreadsheet.

Usage:
    python3 capture_die_image.py --orientation 60 --position 3 --side 5
    python3 capture_die_image.py -o 0 -p 9 -s 1 --die 2 --preview

Saves images into the project data folder (../data/source/obj) by default;
override with --outdir if you want them elsewhere.

Filename format:
    die<DIE>_pos<POSITION>_rot<ORIENTATION>_side<SIDE>_<TIMESTAMP>.jpg

Requires:
    - picamera2 (preinstalled on Raspberry Pi OS Bullseye+ : `sudo apt install python3-picamera2`)
"""

import argparse
import sys
import time
from pathlib import Path

VALID_POSITIONS = set(range(1, 10))       # 1-9, see tracker "Position grid reference"
VALID_ORIENTATIONS = {0, 60, 120, 180, 240, 300}
VALID_SIDES = set(range(1, 7))            # standard six-sided die, 1-6
VALID_DICE = set(range(1, 7))             # up to 6 physical dice


def parse_args():
    parser = argparse.ArgumentParser(
        description="Capture a dice-classifier training image with the Raspberry Pi camera."
    )
    parser.add_argument(
        "-o", "--orientation", type=int, required=True, choices=sorted(VALID_ORIENTATIONS),
        help="Rotation of the die about the global Z axis, in degrees (0, 60, 120, 180, 240, 300)."
    )
    parser.add_argument(
        "-p", "--position", type=int, required=True, choices=sorted(VALID_POSITIONS),
        help="Tray position 1-9 (1=Top-Left ... 9=Center; see tracker spreadsheet for the grid)."
    )
    parser.add_argument(
        "-s", "--side", type=int, required=True, choices=sorted(VALID_SIDES),
        help="Die face currently up (1-6)."
    )
    parser.add_argument(
        "-d", "--die", type=int, default=1, choices=sorted(VALID_DICE),
        help="Which physical die is being photographed (default: 1)."
    )
    parser.add_argument(
        "--outdir", type=str, default=str(Path(__file__).resolve().parents[3] / "data" / "source" / "obj"),
        help="Directory to save the image into (created if it doesn't exist). "
             "Default: <project>/data/source/obj"
    )
    parser.add_argument(
        "--width", type=int, default=1640, help="Capture width in pixels (default: 1640)."
    )
    parser.add_argument(
        "--height", type=int, default=1232, help="Capture height in pixels (default: 1232)."
    )
    parser.add_argument(
        "--preview", action="store_true",
        help="Show a 2-second live preview before capturing (helps with framing/focus)."
    )
    parser.add_argument(
        "--warmup", type=float, default=1.0,
        help="Seconds to let auto-exposure/auto-white-balance settle before capture (default: 1.0)."
    )
    return parser.parse_args()


def build_filename(die: int, position: int, orientation: int, side: int) -> str:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"die{die}_pos{position}_rot{orientation}_side{side}_{timestamp}.jpg"


def main():
    args = parse_args()

    try:
        from picamera2 import Picamera2  # pyright: ignore[reportMissingImports]
        from picamera2.previews.null_preview import NullPreview  # noqa: F401  (import check)  # pyright: ignore[reportMissingImports]
    except ImportError:
        print(
            "ERROR: picamera2 is not installed. On Raspberry Pi OS run:\n"
            "    sudo apt update && sudo apt install -y python3-picamera2\n",
            file=sys.stderr,
        )
        sys.exit(1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(args.die, args.position, args.orientation, args.side)
    filepath = outdir / filename

    picam2 = Picamera2()
    config = picam2.create_still_configuration(
        main={"size": (args.width, args.height)}
    )
    picam2.configure(config)

    try:
        if args.preview:
            picam2.start_preview()
        picam2.start()
        time.sleep(args.warmup)  # let AE/AWB settle so images are consistent
        picam2.capture_file(str(filepath))
    finally:
        picam2.stop()
        if args.preview:
            picam2.stop_preview()

    print(f"Saved: {filepath}")
    print(
        f"  die={args.die}  position={args.position}  orientation={args.orientation} deg  "
        f"side_up={args.side}"
    )


if __name__ == "__main__":
    main()