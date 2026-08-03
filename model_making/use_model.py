import sys

import matplotlib.pyplot as plt

from ultralytics import YOLO

if len(sys.argv) != 2:
    print(f"usage: {sys.argv[0]} /path/to/dice_image.jpg")
    sys.exit(1)

model = YOLO("model_making/yolo26_dice.pt")

results = model.predict(sys.argv[1])

annotated = results[0].plot()
annotated_rgb = annotated[..., ::-1]

plt.imshow(annotated_rgb)
plt.axis("off")
plt.title("YOLO26 dice detection")
plt.show()
