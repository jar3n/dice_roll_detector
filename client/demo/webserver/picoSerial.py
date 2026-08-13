"""
    Class that runs in a thread
    this class will do the following

    maintain a state of the connected pico

    the states are not connected, and connected

    in the connected state it will listen for serial
    messages and send messages using JSON


    @author James Englander


"""

import argparse
from argparse import ArgumentParser, Namespace
import threading
import json
from datetime import datetime
import time
from typing import Any, override
import serial


class SerialSettings():
    """Struct for Serial Device Connection Settings"""
    def __init__(self, port: str, baud: int, timeout:int =1) -> None:
        self._port: str = port
        self._baud: int = baud
        self._timeout: int = timeout

    @property
    def port(self) -> str:
        """Gets the Serial Device Port"""
        return self._port

    @property
    def baud(self) -> int:
        """Gets the Serial Device Baudrate"""
        return self._baud

    @property
    def timeout(self) -> int:
        """Gets the Connection Timeout"""
        return self._timeout


class SerialDiceTray(threading.Thread):
    """Threaded class to listen to serial port
        for the pico and communicate with it
    """

    def __init__(self, port: str, baud: int, timeout: int = 1, debug: bool = False) -> None:
        threading.Thread.__init__(self)
        self.connected: bool = False
        self.serial_settings: SerialSettings = SerialSettings(port, baud, timeout)
        self.serial: serial.Serial | None
        self.lock: threading.Lock = threading.Lock()
        self.data: dict[str, Any] = {  # pyright: ignore[reportExplicitAny]
            "in":"",
            "out":""
        }
        self.running: bool = False
        self.debug: bool = debug

    def initiate_background_process(self) -> None:
        """start thread in the background"""
        self.daemon: bool = True
        self.running = True
        self.start()


    def connect(self) -> None:
        """Attempt to connect to the serial device"""
        try:
            port:str = self.serial_settings.port
            baud:int = self.serial_settings.baud
            timeout:int = self.serial_settings.timeout

            self.serial = serial.Serial(port,
                                        baudrate=baud,
                                        timeout=timeout)
        except serial.SerialException:
            self.serial = None

        with self.lock:
            if self.serial is not None:
                self.connected = True
                print("Connected to device")
            else:
                self.connected = False


    def report(self) -> Any | None:  # pyright: ignore[reportExplicitAny]
        """Report data if there is any then clear it"""

        with self.lock:
            data: Any = self.data['in']  # pyright: ignore[reportAny, reportExplicitAny]
            if self.data['in'] != "":
                self.data['in'] = ""

        return data  # pyright: ignore[reportAny]


    def read(self) -> None:
        """Read the serial data, 
           process it and store it
           in the incoming data buffer
        
        """

        raw: bytes = self.serial.readline()  # pyright: ignore[reportOptionalMemberAccess]
        line: str = raw.decode(encoding="utf-8", errors='ignore').strip()
        if not line:
            # clear input buffer
            # and return None
            self.serial.reset_input_buffer()  # pyright: ignore[reportOptionalMemberAccess]
            with self.lock:
                self.data['in'] = ""
            return

        try:
            data:Any = json.loads(s=line)  # pyright: ignore[reportExplicitAny, reportAny]
            if (self.debug
                    and isinstance(data, dict) and data.get("msg") == "classify"):
                print(f"picoSerial: dice roll detected over serial: {data}")
        except ValueError:
            # failed to decode the line
            # json so its a bad message
            self.serial.reset_input_buffer()  # pyright: ignore[reportOptionalMemberAccess]
            with self.lock:
                self.data['in'] = ""
            return

        with self.lock:
            self.data['in'] = data

    def write(self, msg:Any) -> None: # pyright: ignore[reportExplicitAny, reportAny]
        """Write a message over serial
           by writing to the buffer 
           self.out_going_data

        """
        # pico firmware looks for
        # newline as end of message character
        data: str = json.dumps(obj=msg) + "\n"

        with self.lock:
            self.data['out'] = data

    def stop(self) -> None:
        """stop the thread from running"""
        self.running = False

    @override
    def run(self) -> None:
        """Thread loop"""

        print("Running Pico Serial Thread")


        while self.running:
            try:
                if not self.connected:
                    print("Attempting to connect to device")
                    self.connect()
                    time.sleep(0.5)
                else:
                    if self.serial.in_waiting > 0:  # pyright: ignore[reportOptionalMemberAccess]
                        self.read()
                    elif self.data['out'] != "":
                        _ = self.serial.write( # pyright: ignore[reportOptionalMemberAccess]
                            self.data['out'].encode(encoding="utf-8") # pyright: ignore[reportAny]
                            )
                        with self.lock:
                            self.data['out'] = ""
                    else:
                        time.sleep(0.01)
            except OSError:
                # device disconnected
                # revert to connecting
                self.connected = False

# testing this class below using
# the code from the simple client

def parse_args() -> Namespace:
    """Parse the serial port arguments"""

    parser: ArgumentParser = argparse.ArgumentParser(description=__doc__)

    _ = parser.add_argument(
        "--port", required=True,
        help=("Serial port the board is connected on "
             "(e.g. COM3 on Windows, /dev/ttyACM0 on Linux, /dev/tty.usbmodemXXXX on macOS)"),
    )
    _ = parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")

    return parser.parse_args()

def process_pico_data_helper(pico_data:dict[str, str]) -> bool:
    """Helper function to process the data"""

    try:
        if pico_data['msg'] == "classify":
            return True
    except KeyError:
        print("Got malformed message")

    return False


def main() -> None:
    """Example and test run with the threaded SeralDiceTray Class"""
    complete_msg: dict[str, str] = {
        "msg": "complete"
    }

    args: Namespace = parse_args()

    port:str = args.port  # pyright: ignore[reportAny]
    baud:int = args.baud  # pyright: ignore[reportAny]

    pico_thread: SerialDiceTray = SerialDiceTray(port, baud, timeout=1)

    pico_thread.initiate_background_process()

    waiting = False
    waiting_start: datetime = datetime.now()  # pyright: ignore[reportRedeclaration]
    waiting_duration = 120 # 2 minutes

    try:
        while True:
            if not pico_thread.connected:
                print("No Device connected")
                time.sleep(0.5)
                continue


            pico_data: Any | None = pico_thread.report() # pyright: ignore[reportExplicitAny]
            if pico_data is None:
                time.sleep(0.5)
                continue

            print("Detected incoming data")
            print(f"Incoming data is : {pico_data}")
            # simple interaction to manually
            # send completion message

            is_classify_request: bool = process_pico_data_helper(
                pico_data) # pyright: ignore[reportAny]

            if not is_classify_request:
                continue

            while True:
                if waiting:
                    # check the time elapsed
                    if (datetime.now() - waiting_start).seconds >= waiting_duration:
                        waiting = False
                    else:
                        time.sleep(0.5)
                else:
                    resp: str = input("Wait to send complete message? (y or n)")
                    if resp == "y":
                        waiting = True
                        waiting_start: datetime = datetime.now()
                    else:
                        pico_thread.write(msg=complete_msg)
                        break

    except KeyboardInterrupt:
        pico_thread.stop()
        pico_thread.join(timeout=1)


if __name__ == "__main__":
    main()
