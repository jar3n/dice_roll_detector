#!/usr/bin/env python3
"""
    client-side  dice tray
    performance experiment script.

    Listens for when the dice tray reports 
    a dice roll and records it 
    also counts the number of recorded dice rolls
    and prints that for eace of tracking

    

    @author James Englander
"""

import csv
import json
from pathlib import Path

import serial


DATA_DIR = Path(__file__).resolve().parents[4] / "data" / "experiments" / "dice_tray_performance"


ROLL_COUNT_MAX = 100

report_fieldnames = ["vibe", "vibe settle", "switch 1", "switch 2", "switch 3", "switch 4"]

roll_landing_zones = ["center", "bottom left", "bottom right", "top left", "top right"]
roll_throw_direction = ["left", "right", "front", "back"]

dir_index = 0
zone_index = 0





def main():
    """Listens for dice roll reports"""
    global dir_index, zone_index
    port = input("Serial port (e.g. COM5 or /dev/ttyUSB0): ").strip()
    baud = int(input("Baud rate (e.g. 115200): ").strip())

    default_out = str(DATA_DIR / "data.csv")
    out_path = input(f"CSV output path (default: {default_out}): ").strip() or default_out

    print("\nConnecting...")
    try:
        ser = serial.Serial(port, baudrate=baud, timeout=0.1)
    except serial.SerialException:
        print(f"Failed to connect to device {port}")
        return

    roll_count = 0

    rows = []

    try:

        print(f"Roll from {roll_throw_direction[0]}")
        print(f"Hit {roll_landing_zones[0]} zone ")

        while roll_count < ROLL_COUNT_MAX:
            # listen for roll reports from the firmware
            # and store them

            raw = ser.readline()

            if not raw:
                continue

            try:
                obj = json.loads(raw.decode())
            except (json.JSONDecodeError, ValueError):
                print("skipping malformed data")
                continue

            rows.append(obj)
            roll_count += 1
            print(f"Recorded {roll_count} dice rolls so far")

            if roll_count % 5 == 0 and roll_count > 0:
                dir_index += 1
                if dir_index == len(roll_throw_direction):
                    dir_index = 0
                print(f"Roll from {roll_throw_direction[dir_index]} direction")
            
            if roll_count % 20 == 0 and roll_count > 0:
                zone_index += 1
                if zone_index == len(roll_landing_zones):
                    zone_index = 0
                print(f"Hit {roll_landing_zones[zone_index]} landing zone")

    except KeyboardInterrupt:
        print("Stopped collection early")
        if roll_count == 0:
            print("no data to record, skipping csv write")
    finally:

        if roll_count == 0:
            pass

        # export the reports as csv

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=report_fieldnames)
            w.writeheader()
            w.writerows(rows)
        
        print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
