"""

    Simple script to make
    hailo hef model from the yolo26n model


    @author James Englander




"""



from ultralytics import YOLO

model = YOLO("yolo26_dice.pt")

output = model.export(format="hailo", name="hailo8l")

print(output)
