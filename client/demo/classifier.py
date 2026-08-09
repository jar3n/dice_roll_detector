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

from cv2 import VideoCapture


import time
from pathlib import Path
from typing import Literal
from ultralytics import YOLO
import cv2
import torch

ROOT: Path = Path(__file__).resolve().parent.parent

CAMERA_INDEX = 0
MODEL_PATH: Path = ROOT.joinpath("model_making/yolo26_dice.pt")
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
SETTLE_TIME: float = 1.0  # seconds to let auto-exposure settle after opening the camera
WARMUP_FRAMES = 5  # frames to discard so auto-exposure/gain settles before capture
TORCH_THREADS = 2

# where the captured roll image is written so the web app can serve it
STATIC_DIR: Path = ROOT.joinpath("pi/dicetraywebserver/static")
ROLL_IMAGE_DIR: Path = STATIC_DIR.joinpath("roll_images")
ROLL_IMAGE_PATH: Path = ROLL_IMAGE_DIR.joinpath("latest.jpg")
ROLL_IMAGE_URL = "/static/roll_images/latest.jpg"

_model: YOLO | None = None   # pyright: ignore[reportRedeclaration, reportAssignmentType]

def _load_model() -> YOLO | Literal[True] | None:
    """Lazily load the YOLO detection model once per process."""
    global _model
    if _model is None:
        try:
            torch.set_num_threads(TORCH_THREADS)
            _model: YOLO = YOLO(MODEL_PATH)
        except Exception as exc:
            print(f"classifier: could not load model {MODEL_PATH!r}: {exc}")
            _model = False
    return _model or None


def _capture_frame():
    """Grab one still frame from the camera.

    The first frames from a freshly opened camera are usually too
    dark or too bright while auto-exposure/white-balance converge, so
    a batch of warmup frames is read and discarded before keeping the
    last one.  This keeps brightness consistent from roll to roll.

    Returns:
        numpy.ndarray (BGR) or None if the camera can't be opened.
    """

    cap: VideoCapture = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"classifier: could not open camera index {CAMERA_INDEX}")
        return None
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
        time.sleep(SETTLE_TIME)
        frame = None
        for _ in range(WARMUP_FRAMES):
            ok, frame = cap.read()
            if not ok:
                frame = None
                break
        return frame
    finally:
        cap.release()


def _save_roll_image(image):
    """Save the captured frame (with annotations if any) where the
    web app can serve it.  Failures are non-fatal: classification
    still proceeds without a stored image.

    Returns:
        bool: True if the image was written successfully
    """
    try:
        ROLL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        ok = cv2.imwrite(str(ROLL_IMAGE_PATH), image)
        if ok:
            print(f"classifier: saved roll image to {ROLL_IMAGE_PATH}")
        else:
            print(f"classifier: could not write roll image to {ROLL_IMAGE_PATH}")
        return ok
    except Exception as exc:
        print(f"classifier: could not save roll image: {exc}")
        return False


def classify_roll(data):
    """Entry point called by the web app when the pico reports a roll.

    Args:
        data (dict): the classify message from the pico,
            e.g. {"msg": "classify", "triggers": {...}}.

    Returns:
        dict: {"value": str or None, "image": str or None}.  "value"
        is the die face value, e.g. "5", or None when no die was
        detected.  "image" is the URL of the captured frame the web
        app can display.  Return None to skip the classifier so the
        operator enters the value manually.
    """
    frame = _capture_frame()
    if frame is None:
        return None

    model = _load_model()
    detections = []
    annotated = frame
    if model is not None:
        results = model.predict(frame, verbose=False)
        for r in results:
            for box in r.boxes:
                detections.append({
                    "class": int(box.cls[0]),
                    "conf": float(box.conf[0]),
                    "box": [int(v) for v in box.xyxy[0].tolist()],
                })
        annotated = results[0].plot()

    saved = _save_roll_image(annotated)
    image_url = ROLL_IMAGE_URL if saved else None

    if not detections:
        print("classifier: no dice detected")
        return {"value": None, "image": image_url}

    # Pick the most confident die, then report its face value.
    die = max(detections, key=lambda d: d["conf"])
    value = str(die["class"] + 1)
    print(f"classifier: detected die at {die['box']} -> face value {value}")
    return {"value": value, "image": image_url}