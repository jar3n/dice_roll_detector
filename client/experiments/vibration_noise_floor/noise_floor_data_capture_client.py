# client.py
"""
Client for capturing vibration noise-floor data from the firmware.

- Prompts for serial port/baud and output CSV filename
- Waits for the user to press Enter, then sends "start" over serial
- Streams and parses JSON vibration samples printed by the firmware
  (main.py / test_vibe_noise_floor.py) in a background thread while
  collection runs.  The firmware prints {"vibe":..., "filtered05":...,
  "filtered1":..., "filtered2":..., "filtered3":...} with the EMA filters
  already computed on-device, so the client just records them.
- Timestamps come from the firmware, offset so the first sample is 0
  (falls back to the client clock if the firmware omits a timestamp)
- Automatically stops after COLLECT_DURATION (3 minutes), or on Enter
- Writes timestamp, raw, and per-alpha filtered columns to a CSV file

@author: James Englander
"""

import ast
import csv
import json
import threading
import time
from pathlib import Path

import serial

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "experiments" / "vibe_noise_floor"

# Filter columns produced by the firmware (test_vibe_noise_floor.py),
# keyed by the EMA alpha each one applies.
FILTER_COLUMNS: dict[float, str] = {
    0.05: "filtered05",
    0.1: "filtered1",
    0.2: "filtered2",
    0.3: "filtered3",
}

alpha_list = [0.05, 0.1, 0.2, 0.3]

# How long to collect data (seconds) before stopping automatically.
COLLECT_DURATION = 180


def main():
    port = input("Serial port (e.g. COM5 or /dev/ttyUSB0): ").strip()
    baud = int(input("Baud rate (e.g. 115200): ").strip())

    default_out = str(DATA_DIR / "data.csv")
    out_path = input(f"CSV output path (default: {default_out}): ").strip() or default_out

    print("\nConnecting...")
    ser = serial.Serial(port, baudrate=baud, timeout=0.1)

    # Discard any stale bytes left over from a previous run/boot before
    # we start.
    ser.reset_input_buffer()

    rows = []
    stop_event = threading.Event()
    first_ts: int | None = None

    def process_line(raw):
        nonlocal first_ts
        raw = raw.strip()
        if not raw:
            return

        try:
            obj = json.loads(raw.decode())
        except (json.JSONDecodeError, ValueError):
            # fall back to the old firmware's Python-dict repr
            try:
                obj = ast.literal_eval(raw.decode())
            except (SyntaxError, ValueError):
                print(f"[DEBUG unparsed line] {raw!r}")
                return
        if not isinstance(obj, dict):
            print(f"[DEBUG not a dict] {obj!r}")
            return

        vibe = obj.get("vibe")
        if vibe is None:
            print(f"[DEBUG no 'vibe' key] {obj!r}")
            return

        # Use the firmware's timestamp, offset so the first sample is 0.
        # If the firmware omits a timestamp, fall back to the client clock.
        fw_ts = obj.get("timestamp")
        if fw_ts is None:
            fw_ts = int(time.time() * 1000)
        if first_ts is None:
            first_ts = fw_ts
        ts = fw_ts - first_ts

        out_row = {"timestamp": ts, "raw": vibe}
        for a in alpha_list:
            out_row[FILTER_COLUMNS[a]] = obj.get(FILTER_COLUMNS[a])

        rows.append(out_row)

    def reader_loop():
        buf = b""
        while not stop_event.is_set():
            chunk = ser.read(1024)
            if chunk:
                buf += chunk
                while b"\n" in buf:
                    raw, buf = buf.split(b"\n", 1)
                    process_line(raw)

        # Give any in-flight bytes a moment to arrive after the stop
        # command was sent, then drain whatever's left.
        time.sleep(0.3)
        chunk = ser.read(4096)
        if chunk:
            buf += chunk
        while b"\n" in buf:
            raw, buf = buf.split(b"\n", 1)
            process_line(raw)

    reader_thread = threading.Thread(target=reader_loop, daemon=True)

    input("\nPress Enter to start data collection...")

    # Start the reader before sending "start" so we don't miss any samples
    # that arrive immediately after the firmware begins collecting.
    reader_thread.start()

    ser.write(("start\n").encode())
    print(f"Collecting for {COLLECT_DURATION}s... writing to {out_path}")

    early_stop = threading.Event()

    def wait_for_stop_key():
        input("Press Enter to stop early...")
        early_stop.set()

    threading.Thread(target=wait_for_stop_key, daemon=True).start()

    started_at = time.monotonic()
    while not early_stop.is_set() and time.monotonic() - started_at < COLLECT_DURATION:
        time.sleep(0.2)

    ser.write(("stop\n").encode())
    print("Stopping...")

    stop_event.set()
    reader_thread.join(timeout=2)

    fieldnames = ["timestamp", "raw"] + [FILTER_COLUMNS[a] for a in alpha_list]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Done. Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
