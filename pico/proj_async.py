# utilize the async programming
# model
# use to compare with the synchronous one

from machine import Pin, ADC, PWM
import ujson
import random
import uasyncio as asyncio


# set up peripherals
# pin constants
GREEN_PIN = 13
RED_PIN = 12
YELLOW_PIN = 11
COLL_PIN = 19
VIBE_PIN = 26

red_light = Pin(RED_PIN, Pin.OUT)
yellow_light = Pin(YELLOW_PIN, Pin.OUT)
green_light = Pin(GREEN_PIN, Pin.OUT)

collision = Pin(COLL_PIN, Pin.IN)
vibe = ADC(Pin(26))


# other constants
DEBOUNCE_DELAY = 200
PRINT_DELAY = 1000
NOISE_FLOOR_SAFETY = 700 # 500 plus a bit from observations
SETTLE_TIME = 150
EMA = 0.3


# set up tasks for each peripheral


# traffic light task code
def all_off(r,y,g):
    r.off()
    y.off()
    g.off()


async def control_traffic_light(coll_ev, vibe_ev):
    
    all_off(red_light, yellow_light, green_light)
    # for starters do basic
    # blinking pattern
    while True:
        red_light.toggle()
        await coll_ev.wait()
        red_light.toggle()
        
        yellow_light.toggle()
        await vibe_ev.wait()
        yellow_light.toggle()
        
        green_light.toggle()
        await wait_cleared(coll_ev)
        green_light.toggle()


# collision sensor task code
# returns on press
async def read_collision_sensor(ev):
    prev_val = collision.value()
    
    while True:
        while prev_val == collision.value():
            await asyncio.sleep_ms(4)
        
        current = collision.value()
    
        # trigger the event on falling edge
        # if prev val is 1 and collision i
        if prev_val == 1 and current == 0:
            ev.set()
        
        prev_val = current
        
        await asyncio.sleep_ms(DEBOUNCE_DELAY)
        # cleared by vibration sensor task
    
# vibration sensor task code
# returns on timeout
# as long as timer is not extended

async def read_vibration_sensor(coll_event, vibe_event):
    
    vibe_threshold = NOISE_FLOOR_SAFETY
    
    while True:
        # get initial sample
        vibe_val = vibe.read_u16()
        
        # wait for the collision sensor
        await coll_event.wait()

        # filter the samples using EMA
        vibe_val_now = vibe.read_u16()
        vibe_val = vibe_val_now*EMA + (1-EMA)*vibe_val
       
        # wait for the vibrations to settle
        # because that means the dice stopped rolling
        while vibe_val >= vibe_threshold:
            vibe_val_now = vibe.read_u16()
            vibe_val = vibe_val_now*EMA + (1-EMA)*vibe_val
            await asyncio.sleep_ms(4)
        
        # dice stopped rolling
        # so set the event
        vibe_event.set()
        
        
        # wait for the next
        # impact to clear teh vibration
        # sensor
        # here is where the collision
        # event is cleared
       
        await asyncio.sleep(0)
        coll_event.clear()
        vibe_event.clear()
        
 


# have the main task
# comm with the camera
# json messages
def req_dice_classify():
    
    # have id to confirm its a new request
    id = random.randint(1,10)
    
    return {
        "msg": "classify",
        "id":id
        }

def dice_waiting():
    # have id to confirm its a new request
    id = random.randint(1,10)
    
    
    return {
        "msg": "waiting",
        "id": id
        }

def dice_rolling():
    id = random.randint(1,10)
    
    return {
            "msg": "rolling",
            "id": id
        }


async def wait_cleared(ev):
    # wait for event to clear
    while ev.is_set():
        await asyncio.sleep_ms(4)

async def main():
    # intro hook to the
    # async tasks
    # also manages the
    # communication with the
    # raspberry pi for dice
    # classification
    
    # events
    coll_event = asyncio.Event()
    vibe_event = asyncio.Event()
    
    
    # add tasks here
    asyncio.create_task(control_traffic_light(coll_event, vibe_event))
    asyncio.create_task(read_collision_sensor(coll_event))
    asyncio.create_task(read_vibration_sensor(coll_event, vibe_event))
    
    # main async loop
    while True:
        print(ujson.dumps(dice_waiting()))
        await coll_event.wait()
        print(ujson.dumps(dice_rolling()))
        await vibe_event.wait()
        # send message
        print(ujson.dumps(req_dice_classify()))
        
        # TODO: add in a async function that polls
        # stdin for the response from the pi
        
        # for now just reset the whole thing
        
        
        # this is what resets the whole loop
        # before this will be the camera processing
        await wait_cleared(coll_event)
        
    
# run the whole thing
try:
    asyncio.run(main())
finally:
    all_off(red_light, yellow_light, green_light)
    
    
    
    
    
    

