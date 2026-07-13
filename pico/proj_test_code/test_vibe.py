# use this for characterizing dice roll
# vibrations


from machine import ADC, Pin, PWM
from time import sleep

# pin constants
LED_PIN = 13
VIBE_PIN = 26
SCALE = 1

# pin set up
vibe = ADC(VIBE_PIN)
builtin = PWM(Pin(LED_PIN))
builtin.freq(1000)



# main loop

while True:
    try:
        vibe_val = vibe.read_u16()
        
        builtin.duty_u16(vibe_val*SCALE)
        
        print("vibes", vibe_val)
        sleep(0.1)
        
    except KeyboardInterrupt:
        builtin.duty_u16(0)
        break

