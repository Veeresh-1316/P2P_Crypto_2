import queue
import random
import threading
import time

class PriorityQueueScheduler:
    def __init__(self):
        self.events = queue.PriorityQueue()

    def add_event(self, delay, priority, func, args):
        event = (time.perf_counter() + delay, priority, func, args)
        self.events.put(event)

    def run(self):
        while True:
            next_event_time, priority, func, args = self.events.get()
            current_time = time.perf_counter()
            if current_time < next_event_time:
                time.sleep(next_event_time - current_time)
            func(*args)
