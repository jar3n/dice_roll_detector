"""

    Client that lets me manually
    test the communication between the pico and the client/pi.

    @author James Englander

"""

import argparse
import json
import sys
import serial
import time


def parse_args():
    """Parse the serial port arguments"""

    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--port", required=True,
        help="Serial port the board is connected on "
             "(e.g. COM3 on Windows, /dev/ttyACM0 on Linux, /dev/tty.usbmodemXXXX on macOS)",
    )
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")

    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()

    complete_msg = {
        "msg": "complete"
    }

    try:
        ser = serial.Serial(args.port, args.baud, timeout=1)
    except serial.SerialException as e:
        print(f"Could not open serial port {args.port}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Listening on {args.port} @ {args.baud} baud.. Ctrl+C to stop.")

    try:

        while True:

            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors='ignore').strip()
            if not line:
                continue

            try:
                data = json.loads(line)
                msg = data["msg"]
            except (ValueError, KeyError):
                print(f"Skipping unparseable line: {line}", file=sys.stderr)
                continue

            # immediately respond with message complete
            # for now will add stuff before this
            # have delay to simulate processing
            if msg == "classify":
                print("Recieved classify request. Sending the complete message after two seconds")
                time.sleep(2)
                print("Responding with complete message.")
                # new line indicates end of message
                ser.write((json.dumps(complete_msg) + "\n").encode("utf-8"))



    except KeyboardInterrupt:
        print("Stopped simple client")
