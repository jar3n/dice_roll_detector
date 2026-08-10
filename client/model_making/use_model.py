from argparse import Namespace


import os
import argparse
from typing import cast
from pathlib import Path

import matplotlib.pyplot as plt

from ultralytics import YOLO
from ultralytics.engine.results import Results

def parse_args() -> Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument("imagefile")
    parser.add_argument("--ncnn", action='store_true')


    args = parser.parse_args()

    return args

args = parse_args()

if args.ncnn:
    model = YOLO("yolo26_dice_ncnn_model")
else:
    model = YOLO("yolo26_dice.pt")

image = Path(args.imagefile)

if not os.path.exists(image.resolve().absolute()):
    print(f"Image file {image.resolve().absolute()} does not exist")


else:
    results: list[Results] = [cast(Results, r) for r in model.predict(args.imagefile)]

    annotated = results[0].plot()
    annotated_rgb = annotated[..., ::-1]

    plt.imshow(annotated_rgb)
    plt.axis("off")
    plt.title("YOLO26 dice detection")
    plt.show()
