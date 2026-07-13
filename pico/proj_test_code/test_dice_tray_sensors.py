# testing the sensitivity of the dice tray
# with the combined sensors

# this test is to see how they behave together
# without any laggy printing

# behavior is as expected the collision
# oscillates with the vibration
# instead of bottoming out and being
# closed the whole time the dice is on there
# i think i want to try a mechanical keyboard switch
# so the actuation force is less and the dice weight will
# bottom out the switch



from machine import Pin, ADC, PWM
from time import sleep


# pin constants
COLL_PIN = 19
VIBE_PIN = 26
GREEN_PIN = 13
RED_PIN = 12


#----------
# set up hw
#----------

vibe = ADC(Pin(VIBE_PIN))
collision = Pin(COLL_PIN, Pin.IN)
red_light = PWM(Pin(RED_PIN))
green_light = PWM(Pin(GREEN_PIN))

red_light.freq(1000)
green_light.freq(1000)


def analog_voltage(val):
    return val * 3.3/65535


while True:
    try:
        coll_val = collision.value()
        vibe_val = vibe.read_u16()
        
        red_light.duty_u16(coll_val*50000)
        green_light.duty_u16(vibe_val)
        
        #print("Vibration Sensor Reading", vibe_val)
        #sleep(0.05)
        
        
        
        
    except KeyboardInterrupt:
        red_light.duty_u16(0)
        green_light.duty_u16(0)
        break                  