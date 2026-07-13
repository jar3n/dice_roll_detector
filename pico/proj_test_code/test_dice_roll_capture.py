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

# config constants
NOISE_FLOOR_SAFETY = 10 # noise floor safety factor
SETTLE_TIME = 20 # time for die to stop rolling

# pin set up
vibe = ADC(Pin(VIBE_PIN))
collision = Pin(COLL_PIN, Pin.IN)
red_light = Pin(RED_PIN, Pin.OUT)
green_light = Pin(GREEN_PIN, Pin.OUT)


# setup function
# run once before loop like arduino
# use mainly for noise floor estimation

def setup():
    readings = []
    
    green_light.off()
    red_light.off()

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
            vibe_val = vibe.read_u16()
            
            if coll_val == 0:
                # switch closed
                # start dice settle timer
                die_settle_timer.extend()
                settle_timer_running = True
                red_light.off()
                green_light.on()
            
            if vibe_val >= vibe_threshold and settle_timer_running:
                # if the settle timer is running
                # extend if die has not settled
                die_settle_timer.extend()
            
            
            if die_settle_timer.elapsed():
                # timer has elapsed
                # request picture of the dice
                settle_timer_running = False
                green_light.off()
                red_light.on()
            
    except KeyboardInterrupt:
        green_light.off()
        red_light.off()

main()
        
        
        
            
    
    
    
    

