# utilize the async programming
# model
# use to compare with the synchronous one

from machine import Pin, ADC, PWM
from timer import softTimer
import ujson
import random
import uasyncio as asyncio


# set up tasks for each peripheral


# traffic light task code

# helper 
def all_off(r,y,g):
    r.off()
    y.off()
    g.off()


async def control_traffic_light(r_pin, y_pin, g_pin):
    try:
        # set up
        red_light = Pin(r_pin, Pin.OUT)
        yellow_light = Pin(y_pin, Pin.OUT)
        green_light = Pin(g_pin, Pin.OUT)
        
        # make sure they all start off
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
            await asyncio.sleep_ms(500)
            
    finally:
        all_off(red_light, yellow_light, green_light)

async def main():
    # intro hook to the
    # async tasks
    
    # pin constants
    GREEN_PIN = 13
    RED_PIN = 12
    YELLOW_PIN = 11
    
    # sw constants
    PRINT_DELAY = 1000 
    
    
    # add tasks here
    asyncio.create_task(control_traffic_light(RED_PIN, YELLOW_PIN, GREEN_PIN))
    
    # main async loop
    while True:
        print("I am running an async thing while doing other things!!")
        await asyncio.sleep_ms(PRINT_DELAY)
        
        
    
# run the whole thing
asyncio.run(main())
    
    
    
    
    
    

