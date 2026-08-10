"""
    Dice tray performance firmware
    
    Utilizes the vibration signal processing from
    the vibration threshold testing
    
    The client will tell the firmware when to listen
    for a roll then the firmware will listen
    and tell the client when a roll has occured
    
    as part of reporting, the firmware
    reports whether any switch tripped
    and whether the vibration sensor tripped
    also tells when the roll stopped which is the point when
    the firmware reports to the client
    

    @author James Englander
"""

from machine import Pin, ADC
import uasyncio as asyncio
import ujson as json

# pin constants
VIBE_PIN = 26

SWITCH_PIN_1 = 6
SWITCH_PIN_2 = 7
SWITCH_PIN_3 = 8
SWITCH_PIN_4 = 9


vibe = ADC(Pin(VIBE_PIN))
switch_1 = Pin(SWITCH_PIN_1, Pin.IN, Pin.PULL_DOWN)
switch_2 = Pin(SWITCH_PIN_2, Pin.IN, Pin.PULL_DOWN)
switch_3 = Pin(SWITCH_PIN_3, Pin.IN, Pin.PULL_DOWN)
switch_4 = Pin(SWITCH_PIN_4, Pin.IN, Pin.PULL_DOWN)

switches = [
    (switch_1,1),
    (switch_2,2),
    (switch_3,3),
    (switch_4,4)
    ]

# other constants
DEBOUNCE_DELAY = 200

# vibration signal filtering and
# noise floor constants
NOISE_FLOOR_THRESHOLD = 238 
EMA = 0.05

# state


triggers = {
    "switch 1": False,
    "switch 2": False,
    "switch 3": False,
    "switch 4": False,
    "vibe": False,
    "vibe settle": False 
    }


def poll_vibe_sensor(vibe_val_old):
    """Helper function to poll and filter vibration sensor signal"""
    vibe_val_new = vibe.read_u16()
    vibe_val = EMA*vibe_val_new + (1-EMA)*vibe_val_old
    return vibe_val
    

async def vibe_task():
    """Poll Vibration sensor"""
    global triggers
    vibe_val = vibe.read_u16()
    
    while True:
        
        if not triggers['vibe']:
        
            while vibe_val <= NOISE_FLOOR_THRESHOLD:
                # poll sensor until a dice roll is detected
                vibe_val = poll_vibe_sensor(vibe_val)
                
                
                await asyncio.sleep_ms(4)
            
            triggers['vibe'] = True
        elif not triggers['vibe settle']:
            while vibe_val > NOISE_FLOOR_THRESHOLD:
                # poll sensor until vibrations settle
                vibe_val = poll_vibe_sensor(vibe_val)
                await asyncio.sleep_ms(4)
            
            triggers['vibe settle'] = True
            
            await asyncio.sleep_ms(4)
        
        await asyncio.sleep_ms(4)

async def poll_switch(switch, index):
    """Poll a switch instantiate for each switch"""
    global triggers
    
    prev_val = switch.value()
    
    while True:
        
        while switch.value() == prev_val:
            # wait for trigger 
            await asyncio.sleep_ms(4)
        
        current = switch.value()
        
        if prev_val == 1 and current == 0:
            # on falling edge set trigger
            triggers["switch " + str(index)] = True
        
        prev_val = current
        
        await asyncio.sleep_ms(DEBOUNCE_DELAY)


async def report_dice_roll():
    """print the triggers after dice settle"""
    global triggers
    while True:
        
        if triggers['vibe'] and triggers['vibe settle']:
            # when the vibe and the vibe settle triggers
            # happen print and reset the triggers
            
            print(json.dumps(triggers))
            
            for trigger in triggers.keys():
                triggers[trigger] = False
        
        await asyncio.sleep_ms(40)
        
        
                
async def main():
    
    tasks = [
        asyncio.create_task(vibe_task()),
        asyncio.create_task(poll_switch(*switches[0])),
        asyncio.create_task(poll_switch(*switches[1])),
        asyncio.create_task(poll_switch(*switches[2])),
        asyncio.create_task(poll_switch(*switches[3])),
        asyncio.create_task(report_dice_roll()),
        ]
    
    await asyncio.gather(*tasks)


try:
    asyncio.run(main())
except KeyboardInterrupt:
    asyncio.new_event_loop()
    print()
    print("Stopped")


        
        
    
        




