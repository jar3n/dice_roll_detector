import matplotlib.pyplot as plt

from ultralytics import YOLO

model = YOLO("model_making/yolo26_dice.pt")

results = model.predict("model_making/dice_images/images/die6_pos6_rot240_side6_20260801-214842.jpg")

annotated = results[0].plot()
annotated_rgb = annotated[..., ::-1]

plt.imshow(annotated_rgb)
plt.axis("off")
plt.title("YOLO26 dice detection")
plt.show()
