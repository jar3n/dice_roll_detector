#!/usr/bin/env python3
"""
Flash firmware onto a Raspberry Pi Pico as main.py.

Copies the given firmware file's contents into a local file named
main.py, then uses mpremote to copy that file onto the Pico's
filesystem as main.py, so it runs automatically every time the board
boots.

Usage:
    python flash_pico.py path/to/firmware.py
    python flash_pico.py path/to/firmware.py --port COM5
    python flash_pico.py path/to/firmware.py --reset

Requires mpremote:
    pip install mpremote

@author:
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "firmware_file",
        type=Path,
        help="Path to the firmware .py file to flash onto the Pico",
    )
    parser.add_argument(
        "--port",
        help="Serial port of the Pico (e.g. COM5 or /dev/ttyACM0). "
             "Omit to let mpremote auto-detect it.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Soft-reset the Pico after copying, so main.py starts "
             "running immediately instead of waiting for the next boot.",
    )
    args = parser.parse_args()

    if not args.firmware_file.is_file():
        sys.exit(f"Error: {args.firmware_file} not found")

    if shutil.which("mpremote") is None:
        sys.exit(
            "Error: mpremote not found on PATH.\n"
            "Install it with: pip install mpremote"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        local_main = Path(tmpdir) / "main.py"

        print(f"Copying {args.firmware_file} -> {local_main}")
        shutil.copyfile(args.firmware_file, local_main)

        cmd = ["mpremote"]
        if args.port:
            cmd += ["connect", args.port]
        cmd += ["cp", str(local_main), ":main.py"]
        if args.reset:
            cmd += ["+", "reset"]

        print("Sending to Pico:", " ".join(cmd))
        result = subprocess.run(cmd)

    if result.returncode != 0:
        sys.exit(f"mpremote failed with exit code {result.returncode}")

    print(f"Done. {args.firmware_file.name} is now on the Pico as main.py.")
    if not args.reset:
        print("It will run automatically the next time the Pico boots or is reset.")


if __name__ == "__main__":
    main()