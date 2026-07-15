# utilize the async programming
# model
# use to compare with the synchronous one

from machine import Pin, ADC, PWM
import ujson
import random
import uasyncio as asyncio
#import queue


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

# other constants
DEBOUNCE_DELAY = 200
PRINT_DELAY = 1000 

# queue for shareing data
# though i might change to async events




# set up tasks for each peripheral


# traffic light task code
def all_off(r,y,g):
    r.off()
    y.off()
    g.off()


async def control_traffic_light():
    
    all_off(red_light, yellow_light, green_light)
    # for starters do basic
    # blinking pattern
    while True:
        red_light.toggle()
        await asyncio.sleep_ms(500)
        red_light.toggle()
        
        yellow_light.toggle()
        await asyncio.sleep_ms(500)
        yellow_light.toggle()
        
        green_light.toggle()
        await asyncio.sleep_ms(500)
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
    
        
    

async def main():
    # intro hook to the
    # async tasks
    
    
    # events
    coll_event = asyncio.Event()
    
    
    # add tasks here
    asyncio.create_task(control_traffic_light())
    asyncio.create_task(read_collision_sensor(coll_event))
    
    # main async loop
    while True:
        print("Waiting for collision sensor press")
        await coll_event.wait()
        print("Detected collision sensor press")
        coll_event.clear()        
        
        
    
# run the whole thing
try:
    asyncio.run(main())
finally:
    all_off(red_light, yellow_light, green_light)
    
    
    
    
    
    

