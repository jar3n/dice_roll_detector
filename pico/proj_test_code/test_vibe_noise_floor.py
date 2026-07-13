# script for measuring the ambient vibrations
# detected by the vibration sensor
# useful for determining the threshold
# for the vibration sensor



from machine import Pin, ADC, PWM
from time import sleep, ticks_ms, ticks_diff


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
VIBE_PIN = 26
RED_PIN = 12

# pin set up
vibe = ADC(Pin(VIBE_PIN))
red_light = PWM(Pin(RED_PIN))

# timer set up for noise floor
# measuring
readings = []

print("Initiating noise floor measurements")
noise_floor_timer = softTimer(5000)

sample_rate_timer = softTimer(100)

while not noise_floor_timer.elapsed():
    if sample_rate_timer.elapsed():
        vibe_val = vibe.read_u16()
        readings.append(vibe_val)
        print(vibe_val)
    
    
    

print("Noise floor average: {}".format(sum(readings)/len(readings)))
print("Noise floor max: {}".format(max(readings)))



