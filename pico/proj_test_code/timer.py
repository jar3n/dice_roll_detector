# class for nonblocking timer
from time import ticks_ms, ticks_diff
# non blicking timer class
class softTimer:    
    def __init__(self, period):
        self.period = period
        self.prev_time = ticks_ms()
        self.active = False
    
    def activate(self):
        self.active = True
        
    
    def deactivate(self):
        self.active = False
        
    
    def is_active(self):
        return self.active
    
    def elapsed(self):
        if self.active:
            current = ticks_ms()
            if ticks_diff(current, self.prev_time) >= self.period:
                self.prev_time = current
                return True
            return False
        else:
            return -1
       
    
    def extend(self):
        if self.active:
            self.prev_time = ticks_ms()
        else:
            return -1
    
    def status(self):
        if self.active:
            current = ticks_ms()
            
            lst_str = f"Last Time: {self.prev_time} "
            cur_str = f"Current Time: {current} "
            el_str = f"Elapsed? {ticks_diff(current, self.prev_time) >= self.period}"
            
            return lst_str + cur_str + el_str
        else:
            return "Timer Not Active"
   
