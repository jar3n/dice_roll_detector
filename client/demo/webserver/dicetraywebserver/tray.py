"""
    Shared state for the dice tray web server.

    Owns the SerialDiceTray thread and watches for
    classify requests coming from the pico.  It keeps
    the latest roll result and the "awaiting confirmation"
    state so the web routes can confirm or correct a roll
    before releasing the pico back to polling.

    @author James Englander

"""

import glob
import os
import sys
import threading
import time
from datetime import datetime

# picoSerial.py lives in the pi/ directory, one level up
# from this package.  Make sure it is importable no matter
# which directory flask is started from.
_PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

from picoSerial import SerialDiceTray  # noqa: E402


def camera_available():
    """Return True if the pi has a video device the
       classifier camera could use.
    """
    return bool(glob.glob("/dev/video*"))


def now_iso():
    """Current time as an ISO string for recording results"""
    return datetime.now().isoformat(timespec="seconds")


class TrayState(threading.Thread):
    """Tracks the dice tray serial link and the most recent roll.

    Runs in its own thread: polls the SerialDiceTray report
    buffer for incoming pico messages (classify requests) and
    records the latest roll result and confirmation state.
    """

    POLL_INTERVAL = 0.2

    def __init__(self, dev, baud=115200, tray=None, classify_hook=None):
        threading.Thread.__init__(self, daemon=True)
        self.tray = tray if tray is not None else SerialDiceTray(dev, baud)
        self.classify_hook = classify_hook
        self.running = False
        self.lock = threading.Lock()
        self.awaiting = False
        self.pending_roll = None
        self.pending_result = None
        self.pending_image = None
        self.pending_checked = False
        self.latest_result = None

    def initiate_background_process(self):
        """Start the serial thread and this state thread"""
        self.running = True
        self.tray.initiate_background_process()
        self.start()

    def stop(self):
        """Stop both threads"""
        self.running = False
        self.tray.stop()

    def _handle_classify(self, data):
        """Record a new classify request and ask the
           classifier hook for a result if one is set

        The hook may return a plain value (str or None) or a dict
        {"value": str or None, "image": str or None} so it can also
        hand back a captured image for the dashboard to display.
        """
        with self.lock:
            self.pending_roll = data
            self.awaiting = True
            self.pending_result = None
            self.pending_image = None
            self.pending_checked = False

            if self.classify_hook is not None:
                try:
                    result = self.classify_hook(data)
                    if isinstance(result, dict):
                        self.pending_result = result.get("value")
                        self.pending_image = result.get("image")
                    else:
                        self.pending_result = result
                except Exception:
                    # never let a classifier crash the state thread
                    self.pending_result = None
                    self.pending_image = None
                self.pending_checked = True
                if self.pending_image:
                    print(f"tray: roll image available at {self.pending_image}")

    def run(self):
        """Thread loop: consume messages from the serial thread"""
        print("Running TrayState thread")
        while self.running:
            data = self.tray.report()
            if data and data.get("msg") == "classify":
                self._handle_classify(data)
            time.sleep(self.POLL_INTERVAL)

    def confirm(self):
        """Accept the current (classifier) result and release the pico.

        Returns:
            bool: True if there was a roll awaiting confirmation
        """
        with self.lock:
            if not self.awaiting:
                return False
            if self.pending_result is not None:
                self.latest_result = {
                    "value": str(self.pending_result),
                    "source": "classifier",
                    "entered_at": now_iso(),
                    "image": self.pending_image,
                }
            self.awaiting = False
            self.pending_roll = None
            self.pending_result = None
            self.pending_image = None
            self.pending_checked = False
        self.tray.write({"msg": "complete"})
        return True

    def correct(self, value):
        """Record a corrected/manual result and release the pico.

        Args:
            value (str): the corrected dice roll value

        Returns:
            bool: True if there was a roll awaiting confirmation
        """
        with self.lock:
            if not self.awaiting:
                return False
            self.latest_result = {
                "value": value,
                "source": "correction",
                "entered_at": now_iso(),
                "image": self.pending_image,
            }
            self.awaiting = False
            self.pending_roll = None
            self.pending_result = None
            self.pending_image = None
            self.pending_checked = False
        self.tray.write({"msg": "complete"})
        return True

    def discard(self):
        """Discard the current roll: clear pending state and release the
        pico without recording a result.

        latest_result is left untouched so a previous result stays paired
        with its image.

        Returns:
            bool: True if there was a roll awaiting confirmation
        """
        discarded = False
        with self.lock:
            discarded = self.awaiting
            self.awaiting = False
            self.pending_roll = None
            self.pending_result = None
            self.pending_image = None
            self.pending_checked = False
        if discarded:
            self.tray.write({"msg": "complete"})
        return discarded

    def reset(self):
        """Clear all roll state (awaiting, pending, latest result).

        If the pico was waiting for a classify result, also send it a
        "complete" message so it returns to polling.  If the pico was
        already polling, nothing is written (a stray "complete" would
        sit in its input buffer and swallow the next roll's request).

        Returns:
            bool: True if the pico was released back to polling
        """
        released = False
        with self.lock:
            released = self.awaiting
            self.awaiting = False
            self.pending_roll = None
            self.pending_result = None
            self.pending_image = None
            self.pending_checked = False
            self.latest_result = None
        if released:
            self.tray.write({"msg": "complete"})
        return released

    def status(self):
        """Snapshot of the tray state for the web routes"""
        with self.lock:
            return {
                "camera": camera_available(),
                "tray_connected": self.tray.connected,
                "awaiting": self.awaiting,
                "pending_roll": dict(self.pending_roll) if self.pending_roll else None,
                "pending_result": self.pending_result,
                "pending_image": self.pending_image,
                "pending_checked": self.pending_checked,
                "latest_result": dict(self.latest_result) if self.latest_result else None,
            }


_tray_state = None
_tray_lock = threading.Lock()


def get_tray_state(app=None):
    """Lazily create and start the TrayState singleton.

    Created on the first request so flask's debug reloader
    parent process never grabs the serial port.
    """
    global _tray_state

    if _tray_state is None:
        with _tray_lock:
            if _tray_state is None:
                if app is None:
                    from flask import current_app
                    app = current_app

                tray = TrayState(
                    dev=app.config.get("SERIAL_PORT", "/dev/ttyACM0"),
                    baud=app.config.get("SERIAL_BAUD", 115200),
                    classify_hook=app.config.get("CLASSIFY_HOOK"),
                )
                tray.initiate_background_process()
                _tray_state = tray

    return _tray_state
