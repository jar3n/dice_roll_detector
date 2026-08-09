# script for measuring the ambient vibrations
# detected by the vibration sensor
# useful for determining the threshold
# for the vibration sensor
from machine import Pin, ADC, PWM
import uasyncio as asyncio
import select
import sys
import ujson as json
from time import ticks_ms

# pin constants
VIBE_PIN = 26


# pin set up
vibe = ADC(Pin(VIBE_PIN))


data = {
    "vibe" : None,
    "filtered05": None,
    "filtered1": None,
    "filtered2": None,
    "filtered3": None,
    "timestamp": None
    }

IDLE = 0
COLLECTING = 1

state = IDLE


# Exponential Moving Average
EMAs = [0.05, 0.1, 0.2, 0.3]

SAMPLE_RATE = 50

start_time = 0


def ema(old, new, alpha):
    """calculate exponential moving average"""
    return alpha*new + (1-alpha)*old

async def vibe_task():
    """poll the vibration sensor"""
    global state, data
    while True:
        
        if state == IDLE:
            await asyncio.sleep_ms(40)
            continue
        
        vibe_val = vibe.read_u16()
        
        if data["vibe"] is None:
            """seed all values with initial raw value"""
            for key in data.keys():
                data[key] = vibe_val
            data["timestamp"] = ticks_ms()
            
        else:
            data["vibe"] = vibe_val
            data["filtered05"] = ema(data["filtered05"], vibe_val, EMAs[0])
            data["filtered1"] = ema(data["filtered1"], vibe_val, EMAs[1])
            data["filtered2"] = ema(data["filtered2"], vibe_val, EMAs[2])
            data["filtered3"] = ema(data["filtered3"], vibe_val, EMAs[3])
            data["timestamp"] = ticks_ms()
    
        
        await asyncio.sleep_ms(SAMPLE_RATE)


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



async def cmd_listener_task():
    """Listen for commands from the stdin"""
    global state, data
    while True:
        line = await async_readline()
        if line == "start":
            state = COLLECTING
            
            for key in data.keys():
                data[key] = None
            
        elif line == "stop":
            state = IDLE

async def print_task():
    """Print Data to Terminal"""
    global state, data, start_time
    
    prev_time = start_time
    
    while True:
        if state == IDLE:
            await asyncio.sleep_ms(4) 
        
        else:
            if data["vibe"] is not None and data["timestamp"] > prev_time:
                print(json.dumps(data))
                prev_time = data["timestamp"]
            await asyncio.sleep_ms(SAMPLE_RATE)

async def main():
    tasks = [
            asyncio.create_task(vibe_task()),
            asyncio.create_task(print_task()),
            asyncio.create_task(cmd_listener_task()),
            
        ]
    
    await asyncio.gather(*tasks)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    asyncio.new_event_loop()
        
        
        




