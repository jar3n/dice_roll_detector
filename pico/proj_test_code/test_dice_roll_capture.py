# this is where the timer is incorperated
# need to see how well the current prototype
# detects when dice rolls initiate
# and when they complete


from machine import Pin, ADC, PWM
from time import sleep, ticks_ms, ticks_diff

# non blicking timer class
class softTimer:
    
    def __init__(self, period):
        self.period = period
        self.prev_time = ticks_ms()
    
    def elapsed(self):
        current = ticks_ms()
        if ticks_diff(current, self.prev_time) >= self.period:
            self.prev_time = current
            return True
        return False
    
    def extend(self):
        self.prev_time = ticks_ms()

# pin constants
COLL_PIN = 19
VIBE_PIN = 26
GREEN_PIN = 13
RED_PIN = 12
YELLOW_PIN = 11

# config constants
NOISE_FLOOR_SAFETY = 100 # noise floor safety factor
SETTLE_TIME = 20 # time for die to stop rolling

# pin set up
vibe = ADC(Pin(VIBE_PIN))
collision = Pin(COLL_PIN, Pin.IN)
red_light = Pin(RED_PIN, Pin.OUT)
green_light = Pin(GREEN_PIN, Pin.OUT)
yellow_light = Pin(YELLOW_PIN, Pin.OUT)

# setup function
# run once before loop like arduino
# use mainly for noise floor estimation

def setup():
    readings = []
    
    green_light.value(0)
    red_light.value(1)

    print("Initiating noise floor measurements")
    noise_floor_timer = softTimer(5000)

    sample_rate_timer = softTimer(100)

    while not noise_floor_timer.elapsed():
        if sample_rate_timer.elapsed():
            vibe_val = vibe.read_u16()
            readings.append(vibe_val)
            print(vibe_val)
    
    noise_floor_cap = max(readings)

    print("Noise floor max: {}".format(noise_floor_cap))
    
    
    # pass this 
    return noise_floor_cap


def main():
    vibe_threshold = setup() + NOISE_FLOOR_SAFETY
    die_settle_timer = softTimer(SETTLE_TIME)
    settle_timer_running = False
    
    print("Ready for dice roll detection. Please roll a die.")
    try:
        while True:
    
            coll_val = collision.value()
            
            yellow_light.value(coll_val) # here to track switch state
            
            vibe_val = vibe.read_u16()
            
            if coll_val == 0 and not settle_timer_running:
                # switch closed
                # start dice settle timer
                die_settle_timer.extend()
                settle_timer_running = True
                red_light.value(0)
                green_light.value(1)
                print("detected dice roll start")
            
            if vibe_val >= vibe_threshold and settle_timer_running:
                # if the settle timer is running
                # extend if die has not settled
                die_settle_timer.extend()
            
            
            elif die_settle_timer.elapsed() and settle_timer_running:
                # timer has elapsed
                # request picture of the dice
                settle_timer_running = False
                green_light.value(0)
                red_light.value(1)
                print("detected dice roll end")
            
    except KeyboardInterrupt:
        green_light.value(0)
        red_light.value(0)
        yellow_light.value(0)

main()
        
        
        
            
    
    
    
    

