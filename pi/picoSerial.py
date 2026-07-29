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
import threading
import json
from datetime import datetime
import time
import serial

class SerialDiceTray(threading.Thread):
    """Threaded class to listen to serial port
        for the pico and communicate with it
    """

    def __init__(self, dev, baud, timeout=1):
        threading.Thread.__init__(self)
        self.connected = False
        self.serial_settings = [dev, baud, timeout]
        self.serial = None
        self.lock = threading.Lock()
        self.data = {
            "in":None,
            "out":None
        }
        self.running = False

    def initiate_background_process(self):
        """start thread in the background"""
        self.daemon = True
        self.running = True
        self.start()


    def connect(self):
        """Attempt to connect to the serial device"""
        try:
            self.serial = serial.Serial(*self.serial_settings)
        except serial.SerialException:
            self.serial = None

        with self.lock:
            if self.serial is not None:
                self.connected = True
            else:
                self.connected = False

    def report(self):
        """Report data if there is any then clear it"""

        with self.lock:
            data = self.data['in']
            if self.data['in'] is not None:
                self.data['in'] = None

        return data


    def read(self):
        """Read the serial data, 
           process it and store it
           in the incoming data buffer
        
        """

        raw = self.serial.readline()
        line = raw.decode("utf-8", errors='ignore').strip()
        if not line:
            # clear input buffer
            # and return None
            self.serial.flushInput()
            with self.lock:
                self.data['in'] = None
            return

        try:
            data = json.loads(line)
        except ValueError:
            # failed to decode the line
            # json so its a bad message
            self.serial.flushInput()
            with self.lock:
                self.data['in'] = None
            return

        with self.lock:
            self.data['in'] = data

    def write(self, msg):
        """Write a message over serial
           by writing to the buffer 
           self.out_going_data

        """
        data = json.dumps(msg)

        with self.lock:
            self.data['out'] = data

    def stop(self):
        """stop the thread from running"""
        self.running = False

    def run(self):
        """Thread loop"""

        print("Running Pico Serial Thread")


        while self.running:
            if not self.connected:
                print("Attempting to connect to device")
                self.connect()
                time.sleep(0.5)
            else:
                if self.serial.in_waiting > 0:
                    self.read()
                elif self.data['out'] is not None:
                    self.serial.write(self.data['out'].encode("utf-8"))
                    with self.lock:
                        self.data['out'] = None
                else:
                    time.sleep(0.01)




# testing this class below using
# the code from the simple client

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
    complete_msg = {
        "msg": "complete"
    }

    args = parse_args()

    pico_thread = SerialDiceTray(args.port, args.baud)

    pico_thread.initiate_background_process()

    WAITING = False
    WAITING_START = 0
    WAITING_DURATION = 120 # 2 minutes
    try:
        while True:
            if not pico_thread.connected:
                print("No Device connected")
                time.sleep(0.5)
                continue

            pico_data = pico_thread.report()
            if pico_data is not None:
                print("Detected incoming data")
                # simple interaction to manually
                # send completion message

                try:
                    if pico_data['msg'] == "classify":
                        # decide to wait for two seconds or send the message
                        while True:
                            if WAITING:
                                # check the time elapsed
                                if (datetime.now() - WAITING_START).seconds >= WAITING_DURATION:
                                    WAITING = False
                                else:
                                    time.sleep(0.5)
                            else:
                                resp = input("Wait to send complete message? (y or n)")
                                if resp == "y":
                                    WAITING = True
                                    WAITING_START = datetime.now()
                                else:
                                    pico_thread.write(complete_msg)
                                    break
                except KeyError:
                    print("Recieved malformed message, ignoring and waiting for next")
                    continue
    except KeyboardInterrupt:
        pico_thread.stop()
        pico_thread.join(timeout=1)
