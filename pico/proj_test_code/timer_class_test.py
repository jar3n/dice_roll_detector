from time import ticks_ms, ticks_diff
from machine import Pin

# testing a timer class

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
        
    
builtin = Pin("LED", Pin.OUT)

bt = softTimer(500)

while True:        
    try:
        if bt.elapsed():
            builtin.toggle()
        #bt.extend()
    except KeyboardInterrupt:
        break
    
builtin.off()