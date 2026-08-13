#!/usr/bin/env python3
"""
    Script to collect data for model
    validation. This script takes
    a picture using the camera,
    runs it through the dice classifier,
    shows the operator the captured frame,
    asks them to enter the real (ground
    truth) value, and appends both the
    prediction and the ground truth to a
    CSV log in the data model inference
    performance folder.

    @author James Englander
"""

from sympy.assumptions.assume import Str
from ultralytics.engine.results import Results

from torch._tensor import Tensor

from cv2.typing import MatLike
from ultralytics.models.yolo.model import YOLO


from typing import Iterator, Literal


import csv
import time
from datetime import datetime
from pathlib import Path
from datetime import datetime

import cv2
import torch
from ultralytics import YOLO

ROOT: Path = Path(__file__).resolve().parent.parent.parent.parent.parent

ROLL_IMAGE_DIR: Path = ROOT.joinpath("data/experiments/model_inference_performance")
ROLL_IMAGE_PATH: Path = lambda a, x : ROLL_IMAGE_DIR.joinpath(f"classify{a}real{x}.jpg")
PREDICTIONS_CSV: Path = ROLL_IMAGE_DIR.joinpath("predictions.csv")
MODEL_PATH: Path = ROOT.joinpath("dice_roll_detector/client/model_making")

# model folders and files
PT_MODEL_FILE: Path = MODEL_PATH.joinpath("yolo26_dice.pt")
NCNN_MODEL_FILE: Path = MODEL_PATH.joinpath("yolo26_dice_ncnn_model")
HAILO_MODEL_FILE: Path = MODEL_PATH.joinpath("yolo26_dice_hailo_model")

MODEL_FILES = {
    "pt": PT_MODEL_FILE,
    "ncnn": NCNN_MODEL_FILE,
    "hailo": HAILO_MODEL_FILE,
}

CAMERA_INDEX = 0
CAPTURE_WIDTH = 1920
CAPTURE_HEIGHT = 1080
SETTLE_TIME: float = 1.0  # seconds to let auto-exposure settle after opening the camera
WARMUP_FRAMES = 5  # frames to discard so auto-exposure/gain settles before capture
TORCH_THREADS = 2

_models: dict[str, "YOLO | bool"] = {}


def _load_model(model_type: str, file: Path) -> YOLO | Literal[True] | None:
    """Lazily load a YOLO detection model once per process, cached by type."""
    if model_type not in _models:
        try:
            torch.set_num_threads(TORCH_THREADS)
            _models[model_type] = YOLO(file)
        except Exception as exc:
            print(f"classifier: could not load model {file!r}: {exc}")
            _models[model_type] = False
    loaded = _models[model_type]
    return None if loaded is False else loaded


def _capture_frame():
    """Grab one still frame from the camera.

    The first frames from a freshly opened camera are usually too
    dark or too bright while auto-exposure/white-balance converge, so
    a batch of warmup frames is read and discarded before keeping the
    last one.  This keeps brightness consistent from roll to roll.

    Returns:
        numpy.ndarray (BGR) or None if the camera can't be opened.
    """

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        print(f"classifier: could not open camera index {CAMERA_INDEX}")
        return None
    try:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)  # pyright: ignore[reportUnusedCallResult]
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)  # pyright: ignore[reportUnusedCallResult]
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


def _save_roll_image(image: MatLike, time:datetime, real_val:str) -> bool:
    """Save the captured frame (with annotations if any) where the
    web app can serve it.  Failures are non-fatal: classification
    still proceeds without a stored image.

    Returns:
        bool: True if the image was written successfully
    """
    try:
        ROLL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
        image_file = ROLL_IMAGE_PATH(time, real_val)
        ok = cv2.imwrite(str(image_file), image)
        if ok:
            print(f"classifier: saved roll image to {image_file}")
        else:
            print(f"classifier: could not write roll image to {image_file}")
        return ok
    except Exception as exc:
        print(f"classifier: could not save roll image: {exc}")
        return False


def _predict(model: YOLO, image) -> tuple[str | None, float | None, float | None]:
    """Run the model on the captured frame and return the top prediction.

    Returns:
        (class_name, confidence, inference_ms) for the highest-confidence
        detection, or (None, None, inference_ms) if nothing was detected.
        inference_ms is the wall-clock time of the inference call.
    """
    start = time.perf_counter()
    results: Iterator[Results | Tensor] | list[Results] | list[Tensor] = model(image, verbose=False)  # pyright: ignore[reportUnknownArgumentType]
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    if not results:
        return None, None, elapsed_ms

    result = results[0]  # pyright: ignore[reportIndexIssue]
    boxes = getattr(result, "boxes", None)  # pyright: ignore[reportUnknownArgumentType]
    if boxes is None or len(boxes) == 0:  # pyright: ignore[reportAny]
        return None, None, elapsed_ms

    # pick the highest-confidence detection
    confs = boxes.conf.tolist()  # pyright: ignore[reportAny]
    best_idx = max(range(len(confs)), key=lambda i: confs[i])  # pyright: ignore[reportAny]
    cls_id = int(boxes.cls[best_idx].item())  # pyright: ignore[reportAny]
    conf = float(confs[best_idx])  # pyright: ignore[reportAny]
    class_name = model.names.get(cls_id, str(cls_id))
    return class_name, conf, elapsed_ms


def _fit_to_screen(image: MatLike, max_width: int, max_height: int) -> MatLike:
    """Scale the image down to fit inside the given dimensions, keeping
    the aspect ratio.  Images smaller than the target are left untouched.
    """
    height, width = image.shape[:2]
    scale = min(max_width / width, max_height / height, 1.0)
    if scale >= 1.0:
        return image
    return cv2.resize(
        image,
        (int(width * scale), int(height * scale)),
        interpolation=cv2.INTER_AREA,
    )


def _show_image_for_review(image: MatLike, window_name: str = "Captured Roll"):
    """Display the captured frame so the operator can read the real value.

    The frame is resized to fit on screen so it is never larger than
    the display.  Blocks until any key is pressed, then closes the window.
    """
    try:
        import tkinter

        tk = tkinter.Tk()
        screen_w, screen_h = tk.winfo_screenwidth(), tk.winfo_screenheight()
        tk.destroy()
    except Exception:
        # fall back to a sane default if the screen size can't be queried
        screen_w, screen_h = 1920, 1080

    display_image = _fit_to_screen(image, screen_w, screen_h)
    cv2.imshow(window_name, display_image)
    cv2.waitKey(1)  # let the window actually paint before we ask for input  # pyright: ignore[reportUnusedCallResult]
    return window_name


def _prompt_for_actual_value() -> str:
    """Ask the operator to type in the ground-truth value they see."""
    while True:
        value = input("Enter the actual value shown in the image: ").strip()
        if value:
            return value
        print("Please enter a non-empty value.")


def _csv_header() -> list[str]:
    header = ["timestamp", "image_path", "actual_value"]
    for model_type in MODEL_FILES:
        header += [
            f"{model_type}_predicted",
            f"{model_type}_confidence",
            f"{model_type}_correct",
            f"{model_type}_inference_ms",
        ]
    return header


def _append_prediction_to_csv(
    image_path: Path,
    actual_value: str,
    predictions: dict[str, tuple[str | None, float | None, float | None]],
):
    """Append one row per captured image to the CSV log, with each
    model's prediction/confidence/correctness in its own set of columns.

    Creates the file with a header row if it doesn't exist yet. Models
    that weren't run for this capture are left blank in the row.
    """
    ROLL_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = PREDICTIONS_CSV.exists()

    with open(PREDICTIONS_CSV, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(_csv_header())

        row = [
            datetime.now().isoformat(timespec="seconds"),
            str(image_path),
            actual_value,
        ]
        for model_type in MODEL_FILES:
            predicted_value, confidence, inference_ms = predictions.get(
                model_type, (None, None, None)
            )
            if model_type not in predictions:
                # model wasn't run this capture at all
                row += ["", "", "", ""]
                continue
            correct = (
                str(predicted_value) == str(actual_value)
                if predicted_value is not None
                else False
            )
            row += [
                predicted_value if predicted_value is not None else "",
                f"{confidence:.4f}" if confidence is not None else "",
                correct,
                f"{inference_ms:.1f}" if inference_ms is not None else "",
            ]
        writer.writerow(row)

    print(f"classifier: logged prediction to {PREDICTIONS_CSV}")


def run(model_types: list[str]):
    frame = _capture_frame()
    if frame is None:
        print("classifier: aborting, no frame captured")
        return

    # run every requested model against the same captured frame
    predictions: dict[str, tuple[str | None, float | None, float | None]] = {}
    for model_type in model_types:
        model = _load_model(model_type, MODEL_FILES[model_type])
        if model is None:
            print(f"classifier: skipping '{model_type}', model failed to load")
            predictions[model_type] = (None, None, None)
            continue

        predicted_value, confidence, inference_ms = _predict(model, frame)  # pyright: ignore[reportArgumentType]
        predictions[model_type] = (predicted_value, confidence, inference_ms)
        if predicted_value is not None:
            print(
                f"classifier: [{model_type}] predicted '{predicted_value}' "  # pyright: ignore[reportImplicitStringConcatenation]
                f"(confidence {confidence:.2f}, inference {inference_ms:.1f} ms)"  # pyright: ignore[reportImplicitStringConcatenation]
            )
        else:
            print(
                f"classifier: [{model_type}] no detection found in frame "  # pyright: ignore[reportImplicitStringConcatenation]
                f"(inference {inference_ms:.1f} ms)"  # pyright: ignore[reportImplicitStringConcatenation]
            )

    # show the operator the frame once and ask for the ground truth once,
    # it applies to every model's prediction for this capture
    window_name = _show_image_for_review(frame)
    actual_value = _prompt_for_actual_value()
    cv2.destroyWindow(window_name)

    _save_roll_image(frame, datetime.now(), actual_value)  # pyright: ignore[reportUnusedCallResult]

    _append_prediction_to_csv(
        image_path=ROLL_IMAGE_PATH,
        actual_value=actual_value,
        predictions=predictions,
    )


if __name__ == "__main__":
    run(sorted(MODEL_FILES.keys()))