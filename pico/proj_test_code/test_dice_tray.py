# testing the dice tray can detect anything

from machine import Pin, ADC,PWM
from time import sleep

#----------
# set up sensors
#----------

vibe = ADC(Pin(26))
collision = Pin(19, Pin.IN)


builtin = Pin("LED", Pin.OUT)

def analog_voltage(val):
    return val * 3.3/65535

#--------------
# file setup
#---------------

#csv = open("vibe.csv","w")
#csv.write("time, vibe readout\n")

# --------
# time setup
# doing a basic loop counter
# --------

#time = 0

while True:
    try:
        #knock_val = mc.read_u16()
        vibe_val = vibe.read_u16()
        
        builtin.value(collision.value())
        
        #csv.write("{},{},{}\n".format(knock_val, vibe_val, ticks_ms()))
        
        
        #csv.write("{},{}\n".format(time, analog_voltage(vibe_val)))
        #time += 1
        
        
        #print("Collision Sensor Reading", collision.value())
        print("Vibration Sensor Reading", vibe_val)
        sleep(0.05)
        
        
    except KeyboardInterrupt:
        break

csv.close()
                  