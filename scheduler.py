import queue
import time

### Use the synchronised python priority queue for scheduling process
### Efficient when delay is small 
class PriorityQueueScheduler:
    def __init__(self):
        self.events = queue.PriorityQueue()
        

    def add_event(self, delay,func, args):
        event = (time.perf_counter() + delay, 1 , func, args)
        self.events.put(event)

    def run(self):
        while True:
            next_event_time, priority, func, args = self.events.get()
            current_time = time.perf_counter()
            if current_time < next_event_time:
                time.sleep(next_event_time - current_time)
            func(*args)

### Discrete event simulator that waits for some time until it finds a 
### event to execute . Useful for high delay callbacks
MIN_SLEEP = 0.5
class DiscretEventScheduler :
    def __init__(self):
        self.events = queue.PriorityQueue()
        
    def add_event(self, delay,func, args):
        # print( func , args , delay )
        event = (time.perf_counter() + delay, 1 , func, args)
        self.events.put(event)

    def run(self) :
        while True:
            if self.events.empty() : 
               time.sleep(MIN_SLEEP)
               continue
            next_event_time, priority, func, args = self.events.queue[0]
            current_time = time.perf_counter()
            if current_time < next_event_time:
                time.sleep( min(next_event_time - current_time , MIN_SLEEP) )
            else : 
                self.events.get()
                # print("exec" , func , args , next_event_time - current_time )
                func(*args)