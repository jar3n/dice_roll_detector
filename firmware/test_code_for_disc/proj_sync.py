# code for project not using async
# programming

# set up is to use multithreading
# have one thread for the vibration sensor
# have the other for reporting and collision sensor

# this is where the timer is incorperated
# need to see how well the current prototype
# detects when dice rolls initiate
# and when they complete

from machine import Pin, ADC, PWM
from timer import softTimer
import _thread
import ujson
import random



# pin constants
COLL_PIN = 19
VIBE_PIN = 26
GREEN_PIN = 13
RED_PIN = 12
YELLOW_PIN = 11

# config constants
NOISE_FLOOR_SAFETY = 500   # noise floor safety factor
SETTLE_TIME = 150          # time for die to stop rolling
PRINT_DELAY = 1000         # time between status updates
DEBOUNCE_DELAY = 200       # min time between valid collision triggers
EMA = 0.3 # exponential weighted average alpha

# pin set up
vibe = ADC(Pin(VIBE_PIN))
collision = Pin(COLL_PIN, Pin.IN)
red_light = Pin(RED_PIN, Pin.OUT)
green_light = Pin(GREEN_PIN, Pin.OUT)
yellow_light = Pin(YELLOW_PIN, Pin.OUT)

# timers
die_settle_timer = softTimer(SETTLE_TIME)
debounce_timer = softTimer(DEBOUNCE_DELAY)
debounce_timer.activate()  # always active

# state management
NOISE_FLOOR = 0
WAITING = 1
ROLLING = 2
state = NOISE_FLOOR

# thread stuff
stop_flag = False
lock = _thread.allocate_lock()


# setup function
# run once before loop like arduino
# use mainly for noise floor estimation
def setup():
    readings = []
    print("Initiating noise floor measurements")
    noise_floor_timer = softTimer(5000)
    noise_floor_timer.activate()
    sample_rate_timer = softTimer(100)
    sample_rate_timer.activate()

    while not noise_floor_timer.elapsed():
        if sample_rate_timer.elapsed():
            vibe_val = vibe.read_u16()
            readings.append(vibe_val)
            print(vibe_val)

    sample_rate_timer.deactivate()
    noise_floor_timer.deactivate()

    noise_floor_cap = max(readings)
    print("Noise floor max: {}".format(noise_floor_cap))

    return noise_floor_cap

# json messages
def req_dice_classify():
    
    # have id to confirm its a new request
    id = random.randint(1,10)
    
    return {
        "msg": "classify",
        "id":id
        }


# threading function to print
def printing_thread():
    # simply prints the status
    # of the die settle timer
    global die_settle_timer, state, stop_flag

    print_timer = softTimer(PRINT_DELAY)
    print_timer.activate()
    
    prev_state = NOISE_FLOOR
    
    while not stop_flag:
        lock.acquire()
        curr_state = state
        lock.release()
        
        if prev_state != state:
            if state == WAITING and prev_state == ROLLING:
                # this is the end of the dice roll
                # so now send the json message that the dice has
                # been rolled
                # and is ready to be captured
                print(ujson.dumps(req_dice_classify()))
            
            
            # update prev state
            prev_state = state
                
                
        


def main():
    global stop_flag, state

    vibe_threshold = setup() + NOISE_FLOOR_SAFETY
    print(f"Vibe threshold set to: {vibe_threshold}")

    _thread.start_new_thread(printing_thread, ())

    state = WAITING

    green_light.value(0)
    red_light.value(1)

    prev_coll_val = 1
    
    vibe_val = vibe.read_u16()

    try:
        while True:

            coll_val = collision.value()
            yellow_light.value(coll_val)  # here to track switch state

            vibe_val_now = vibe.read_u16()
            # apply exponential moving average here
            vibe_val = EMA* vibe_val_now + (1-EMA)*vibe_val

            green_light.value(die_settle_timer.active)
            red_light.value(not die_settle_timer.active)

            # edge-triggered + debounced collision detection
            if (coll_val == 0 and prev_coll_val == 1
                    and not die_settle_timer.is_active()
                    and debounce_timer.elapsed()):
                debounce_timer.extend()
                die_settle_timer.activate()
                die_settle_timer.extend()
                state = ROLLING

            if vibe_val >= vibe_threshold and die_settle_timer.is_active():
                die_settle_timer.extend()

            if die_settle_timer.elapsed() and die_settle_timer.is_active():
                # timer has elapsed
                # request picture of the dice
                die_settle_timer.deactivate()
                state = WAITING

            prev_coll_val = coll_val

    except KeyboardInterrupt:
        green_light.value(0)
        red_light.value(0)
        yellow_light.value(0)
        stop_flag = True


main()
