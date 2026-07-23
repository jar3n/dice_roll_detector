"""

    Firmware to run on the pico
    for the dice tray.
    
    This firmware polls all the sensors
    and detects a dice roll then requests
    a classification. It waits for the
    result before resetting.
    
    
    @author James Englander


"""

from machine import Pin, ADC
import ujson
import uasyncio as asyncio
import sys
import select


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
vibe = ADC(Pin(VIBE_PIN))


# other constants
DEBOUNCE_DELAY = 200
NOISE_FLOOR_SAFETY = 700 # 500 plus a bit from observations
EMA = 0.3

# shared state
POLLING = 0
ROLLING = 1
WAITING = 2

state = {
    "current": POLLING
    }

def all_off(r,y,g):
    r.off()
    y.off()
    g.off()
    
def switch_on(r,y,g, on):
    
    if on == "r":
        r.on()
        y.off()
        g.off()
    elif on == "y":
        r.off()
        y.on()
        g.off()
    elif on == "g":
        r.off()
        y.off()
        g.on()


# task to controll traffic light
# which provides a simple visual
# for easy state tracking
async def control_traffic_light():
    
    all_off(red_light, yellow_light, green_light)
    # for starters do basic
    # blinking pattern
    while True:
        if state["current"] == POLLING:
            switch_on(red_light, yellow_light, green_light, "r")
        elif state["current"] == ROLLING:
            switch_on(red_light, yellow_light, green_light, "y")
        elif state["current"] == WAITING:
            switch_on(red_light, yellow_light, green_light, "g")
        
        await asyncio.sleep_ms(40)
        
# task to poll the collision sensor
# and change the state when
# a dice hits the tray
async def poll_collision_sensor():
    prev_val = collision.value()
    
    while True:
        
        if state["current"] != POLLING:
            # wait to return to sensor polling state
            # before polling collision sensor
            await asyncio.sleep_ms(40)
        else:
            # poll for a dice impact
            while prev_val == collision.value():
                await  asyncio.sleep_ms(40)
                
            current = collision.value()
        
            if prev_val == 1 and current== 0:
                #detected falling edge so
                # change state to ROLLING
                state["current"] = ROLLING
                
            
            prev_val = current
            
            await asyncio.sleep_ms(DEBOUNCE_DELAY)
    

# task to poll the vibration sensor
# when the die is rolling on the tray
async def poll_vibration_sensor():
    
    vibe_threshold = NOISE_FLOOR_SAFETY
    
    while True:
        
        if state["current"] != ROLLING:
            # wait for initial impact
            # to poll for vibrations
            await asyncio.sleep_ms(40)
        
        else:
            # get initial sample
            vibe_val = vibe.read_u16()
            
            while vibe_val >= vibe_threshold:
                
                # exponential mean filter samples
                # after first
                vibe_val_now = vibe.read_u16()
                vibe_val = vibe_val_now*EMA + (1-EMA)*vibe_val
                
                await asyncio.sleep_ms(4)
            
            # at this point die stopped rolling
            # and tray vibes have settled
            # so wait for the dice roll
            # classification
            state["current"] = WAITING
            
            # safety yeild at end of this
            # when returning to the task
            # it should yield from above
            await  asyncio.sleep_ms(4)


# helper task
# to read from stdin
# asynchronously
poll_obj = select.poll()
poll_obj.register(sys.stdin, select.POLLIN)

async def async_readline():
    """Non-blocking-ish line reader: yields to other tasks
    while waiting for a full line on stdin."""
    line = ''
    while True:
        if poll_obj.poll(0):          # 0 = don't block, just check
            ch = sys.stdin.read(1)    # safe to read since poll said ready
            if ch in ('\n', '\r'):
                if line:
                    return line
                # ignore stray \r or \n with nothing buffered yet
            else:
                line += ch
        else:
            await asyncio.sleep_ms(10)

# task to communicate with the
# client which will do the
# dice roll classification
async def comm_with_client():
    
    classify_request = {
                    "msg": "classify"
                }
    
    request_sent = False
    
    while True:
        
        if state["current"] != WAITING:
            await asyncio.sleep_ms(40)
            continue
    
        
        # send the request
        if not request_sent:
            print(ujson.dumps(classify_request))
            request_sent = True
        
        line = await async_readline()
        
        # parse the line
        try:
            data = ujson.loads(line)
            msg = data["msg"]
        except (KeyError, ValueError):
            continue
        
    
        # on receipt return to polling
        # for die
        if msg == "complete":
            state["current"] = POLLING
            request_sent = False
        else:
            # unrecognized message
            pass
      
        
        # yeild 
        await asyncio.sleep_ms(4)

# spawn all the tasks                
async def main():
    
    tasks = [
        asyncio.create_task(control_traffic_light()),
        asyncio.create_task(poll_collision_sensor()),
        asyncio.create_task(poll_vibration_sensor()),
        asyncio.create_task(comm_with_client())
        ]
        
    await asyncio.gather(*tasks)

            

try:
    asyncio.run(main())
except KeyboardInterrupt:
    asyncio.new_event_loop()
    all_off(red_light, yellow_light, green_light)
            
    



