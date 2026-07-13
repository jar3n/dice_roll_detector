# code for project not using async
# programming

# set up is to use multithreading
# have one thread for the vibration sensor
# have the other for reporting and collision sensor

from machine import Pin, ADC
from time import sleep, ticks_ms, ticks_diff


# pin set up
vibe = ADC(Pin(26))
collision = Pin(19, Pin.IN, Pin.PULL_DOWN)
builtin = Pin("LED", Pin.OUT)

