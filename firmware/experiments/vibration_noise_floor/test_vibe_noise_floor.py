# script for measuring the ambient vibrations
# detected by the vibration sensor
# useful for determining the threshold
# for the vibration sensor



from machine import Pin, ADC, PWM
import uasyncio as asyncio


# pin constants
VIBE_PIN = 26
RED_PIN = 12

# pin set up
vibe = ADC(Pin(VIBE_PIN))
red_light = PWM(Pin(RED_PIN))

# timer set up for noise floor
# measuring
readings = []

print("Initiating noise floor measurements")
noise_floor_timer = softTimer(30000)

sample_rate_timer = softTimer(100)

while not noise_floor_timer.elapsed():
    if sample_rate_timer.elapsed():
        vibe_val = vibe.read_u16()
        readings.append(vibe_val)
        print(vibe_val)
    
    
    

print("Noise floor average: {}".format(sum(readings)/len(readings)))
print("Noise floor max: {}".format(max(readings)))



