# client.py
"""
Client for capturing vibration noise-floor data from the firmware.

- Prompts for serial port/baud, output CSV filename, and EMA alphas
- Waits for the user to press Enter, then sends {"cmd":"start","timestamp":...}
- Streams and parses JSON vibration samples ({"raw":...,"timestamp":...})
  in a background thread while collection is running
- Waits for the user to press Enter again, then sends {"cmd":"stop"}
- Computes an EMA of the raw signal for each requested alpha
- Writes timestamp, raw, and per-alpha EMA columns to a CSV file

@author: James Englander
"""

import json
import time
import csv
import threading
from pathlib import Path

import serial

DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "datafiles"


def main():
    port = input("Serial port (e.g. COM5 or /dev/ttyUSB0): ").strip()
    baud = int(input("Baud rate (e.g. 115200): ").strip())

    default_out = str(DATA_DIR / "data.csv")
    out_path = input(f"CSV output path (default: {default_out}): ").strip() or default_out

    alpha_in = input(
        "EMA alphas (comma-separated, e.g. 0.05,0.1,0.2). "
        "Default: 0.05,0.1,0.2,0.3: "
    ).strip()
    if not alpha_in:
        alpha_list = [0.05, 0.1, 0.2, 0.3]
    else:
        alpha_list = [float(s) for s in alpha_in.split(",")]

    for a in alpha_list:
        if a <= 0 or a > 1:
            raise ValueError("All alpha values must be in (0, 1].")

    alpha_list = sorted(alpha_list)
    print(f"EMA enabled for alphas={alpha_list}")

    print("\nConnecting...")
    ser = serial.Serial(port, baudrate=baud, timeout=0.1)

    # Discard any stale bytes left over from a previous run/boot before
    # we start.
    ser.reset_input_buffer()

    rows = []
    emas = {a: None for a in alpha_list}
    stop_event = threading.Event()

    def process_line(raw):
        raw = raw.strip()
        if not raw:
            return

        try:
            obj = json.loads(raw.decode())
        except Exception:
            return

        if "raw" not in obj or "timestamp" not in obj:
            return

        x = obj["raw"]
        ts = obj["timestamp"]

        out_row = {"timestamp": ts, "raw": x}
        for a in alpha_list:
            if emas[a] is None:
                emas[a] = float(x)
            else:
                emas[a] = a * x + (1.0 - a) * emas[a]
            out_row[f"ema_{a}"] = emas[a]

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

    start_ts = int(time.time() * 1000)  # ms epoch
    cmd = {"cmd": "start", "timestamp": start_ts}
    ser.write((json.dumps(cmd) + "\n").encode())
    print(f"Collecting... writing to {out_path}")

    input("Press Enter to stop data collection...")

    stop_cmd = {"cmd": "stop"}
    ser.write((json.dumps(stop_cmd) + "\n").encode())
    print("Stopping...")

    stop_event.set()
    reader_thread.join(timeout=2)

    fieldnames = ["timestamp", "raw"] + [f"ema_{a}" for a in alpha_list]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"Done. Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()