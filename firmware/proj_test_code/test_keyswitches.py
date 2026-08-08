"""

    Simple script to
    test the keyswitch based
    design for the dice tray
    
    @author James Englander


"""

from machine import Pin, ADC
from time import sleep

# Key Switches and vibe set up

VIBE_PIN = 26

SWITCH_1 = 6
SWITCH_2 = 7
SWITCH_3 = 8
SWITCH_4 = 9

vibe = ADC(Pin(VIBE_PIN))

switch_1 = Pin(SWITCH_1, Pin.PULL_DOWN)
switch_2 = Pin(SWITCH_2, Pin.PULL_DOWN)
switch_3 = Pin(SWITCH_3, Pin.PULL_DOWN)
switch_4 = Pin(SWITCH_4, Pin.PULL_DOWN)


try:
    while True:
        
        vals = [switch_1.value(), switch_2.value(), switch_3.value(), switch_4.value(), vibe.read_u16()]
        
        print("Switch_1", vals[0],"Switch_2", vals[1],"Switch_3", vals[2],"Switch_4", vals[3])
        sleep(0.05)
except KeyboardInterrupt:
    print("Stopped")
    pass


        
