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
            port = self.serial_settings[0]
            baud = self.serial_settings[1]
            timeout = self.serial_settings[2]
            self.serial = serial.Serial(port, baud, timeout=timeout)
        except serial.SerialException:
            self.serial = None

        with self.lock:
            if self.serial is not None:
                self.connected = True
                print("Connected to device")
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
        # pico firmware looks for
        # newline as end of message character
        data = json.dumps(msg) + "\n"

        with self.lock:
            self.data['out'] = data

    def stop(self):
        """stop the thread from running"""
        self.running = False

    def run(self):
        """Thread loop"""

        print("Running Pico Serial Thread")


        while self.running:
            try:
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
            except OSError:
                # device disconnected
                # revert to connecting
                self.connected = False

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

def process_pico_data_helper(pico_data):
    """Helper function to process the data"""

    try:
        if pico_data['msg'] == "classify":
            return True
    except KeyError:
        print("Got malformed message")

    return False


def main():
    """Example and test run with the threaded SeralDiceTray Class"""
    complete_msg = {
        "msg": "complete"
    }

    args = parse_args()

    pico_thread = SerialDiceTray(args.port, args.baud)

    pico_thread.initiate_background_process()

    waiting = False
    waiting_start = 0
    waiting_duration = 120 # 2 minutes

    try:
        while True:
            if not pico_thread.connected:
                print("No Device connected")
                time.sleep(0.5)
                continue


            pico_data = pico_thread.report()
            if pico_data is None:
                time.sleep(0.5)
                continue

            print("Detected incoming data")
            print(f"Incoming data is : {pico_data}")
            # simple interaction to manually
            # send completion message

            is_classify_request = process_pico_data_helper(pico_data)

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
                    resp = input("Wait to send complete message? (y or n)")
                    if resp == "y":
                        waiting = True
                        waiting_start = datetime.now()
                    else:
                        pico_thread.write(complete_msg)
                        break

    except KeyboardInterrupt:
        pico_thread.stop()
        pico_thread.join(timeout=1)


if __name__ == "__main__":
    main()
