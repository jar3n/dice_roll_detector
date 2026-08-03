"""
classifier.py

Standalone dice classifier hook for the dice tray web app.

The Flask server calls classify_roll() whenever the pico reports a roll
(see CLASSIFY_HOOK in dicetraywebserver/__init__.py and tray.py).  Keeping
the classifier in its own file lets you iterate on the model, camera, and
pip-reading logic without touching the web app.

Wire it up in pi/instance/config.py:

    from classifier import classify_roll
    CLASSIFY_HOOK = classify_roll

That import works because pi/ is put on sys.path by
dicetraywebserver/tray.py (the parent of the web package).
"""

import time
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parent.parent

CAMERA_INDEX = 0
MODEL_PATH = ROOT.joinpath("model_making/yolo26_dice.pt")
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
SETTLE_TIME = 1.0  # seconds to let auto-exposure settle after opening the camera

_model = None


def _load_model():
    """Lazily load the YOLO detection model once per process."""
    global _model
    if _model is None:
        try:
            from ultralytics import YOLO

            _model = YOLO(MODEL_PATH)
        except Exception as exc:
            print(f"classifier: could not load model {MODEL_PATH!r}: {exc}")
            _model = False
    return _model or None


def _capture_frame():
    """Grab one still frame from the camera.

    Returns:
        numpy.ndarray (BGR) or None if the camera can't be opened.
    """

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"classifier: could not open camera index {CAMERA_INDEX}")
        return None
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
        time.sleep(SETTLE_TIME)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def _detect_dice(frame):
    """Run object detection and return the dice found.

    Returns:
        list of detections, each as a dict with keys
        "class" (int), "conf" (float), and "box" (x1, y1, x2, y2).
        Empty list if the model isn't available or finds nothing.
    """
    model = _load_model()
    if model is None:
        return []

    results = model.predict(frame, verbose=False)
    detections = []
    for r in results:
        for box in r.boxes:
            detections.append({
                "class": int(box.cls[0]),
                "conf": float(box.conf[0]),
                "box": [int(v) for v in box.xyxy[0].tolist()],
            })
    return detections


def classify_roll(data):
    """Entry point called by the web app when the pico reports a roll.

    Args:
        data (dict): the classify message from the pico,
            e.g. {"msg": "classify", "triggers": {...}}.

    Returns:
        str: the die face value, e.g. "5".  Return None to skip the
        classifier so the operator enters the value manually.
    """
    frame = _capture_frame()
    if frame is None:
        return None

    detections = _detect_dice(frame)
    if not detections:
        print("classifier: no dice detected")
        return None

    # Pick the most confident die, then report its face value.
    die = max(detections, key=lambda d: d["conf"])
    value = str(die["class"] + 1)
    print(f"classifier: detected die at {die['box']} -> face value {value}")
    return value
