# for testing collision sensor/mechanical keyboard switch
# will be used to see what i need for it

# using the built in led instead of printing because
# printing is super taxing on the pico

# observations from using it is that I can see
# the led is default on because the collision sensor
# is 1 when open and 0 when closed

# the current prototype as of july 13th behavior:
# the die impact triggers the collision sensor but the sensor
# needs a higher minimum actuation force to keep the
# sensor closed.

# continuing with this prototype means the collision sensor
# acts as a trigger to listen to the vibrations
# when the vibrations decay then the die has stopped rolling
# and the picture can be taken

# with lower actuation force switch, the behavior could be thus
# the collision sensor stays down until the die is removed
# from the tray rather than popping up after the first impact
# means the vibrations stop but there is  confirmation the die
# is still in the tray.

# tradeoff is that the switch would vibrate until settling
# as well maybe causing reduncancy

from machine import Pin
from time import sleep


# constants for ease of use
COLL_PIN = 19
LED_PIN = "LED"


# pin set up
collision = Pin(COLL_PIN, Pin.IN, Pin.PULL_UP)
builtin = Pin(LED_PIN, Pin.OUT)


# main loop
while True:
    try:
        #print("Collision Sensor Value", collision.value())
        builtin.value(collision.value())
    except KeyboardInterrupt:
        break

builtin.off()


