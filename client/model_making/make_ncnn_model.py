"""
    
    Simple script to make an NCNN model file
    from the pytorch file.

    The NCNN model file is a binary model file
    made for edge devices by Ultralytics that 
    aims to be more optimized for low resource use

    @author James Englander

"""


from ultralytics import YOLO




pt_model = YOLO("yolo26_dice.pt")

pt_model.export(format="ncnn")

