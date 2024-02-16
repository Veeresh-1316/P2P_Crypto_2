from collections import defaultdict
import hashlib
from multiprocessing import Pool
from multiprocessing import pool
from multiprocessing.pool import ThreadPool
import random
import numpy as np
import simpy
import time
from graph import generate_random_connected_graph
from threading import Thread
from scheduler import PriorityQueueScheduler

scheduler = PriorityQueueScheduler()
scheduler_thread = Thread(target=scheduler.run)
scheduler_thread.start()

interarrival_mean_time = 9
coins_per_transaction = 1
size_of_transaction = 8    # kilo-bits
N = 5
z0 = 0.5
z1 = 0.5
rho = random.random()*490 + 10     # ms - light propagation delay

peers = []
peers_slow = np.random.choice(N, int(z0*N), replace=False)
peers_low_cpu = np.random.choice(N, int(z1*N), replace=False)

start = time.perf_counter()

all_transactions = []
class Transaction:
    def __init__(self, sender, receiver, coins):
        self.timestamp = time.perf_counter()
        self.txid = hashlib.md5((str(random.randint(1,100))+str(self.timestamp)).encode('utf-8')).hexdigest()
        self.sender = sender
        self.receiver = receiver
        self.coins = coins
        self.status = False
        all_transactions.append(self)
        
    def __hash__(self) -> int:
        return hash(self.txid) 
    
    def __repr__(self):
        #TxnID: IDx pays IDy C coins
        return f"{self.txid}: {self.sender} pays {self.receiver} {self.coins} coins"

class Peer:
    def __init__(self, speed, cpu):
        self.speed = speed
        self.cpu = cpu
        self.id = len(peers)
        peers.append(self)
        self.bitcoins = 10
        self.transactions = []
        self.queue = defaultdict(time.perf_counter)
        self.connections = []
         
    def generate(self, env):
        while True:
            tim = np.random.exponential(interarrival_mean_time)
            yield env.timeout(tim)
            tx = Transaction(self, random.choice(peers[:self.id]+peers[self.id+1:]), coins_per_transaction)
            self.transactions.append(tx)
            print("Generating by ", self.id, "at ", time.perf_counter() - start)
            print(tx)
            thread = Thread(target=self.broadcast, args=(tx,))
            thread.start()

    def get_latency(self, peer, size):
        c_ij = 100 if (self.speed and peer.speed) else 5
        d_ij = np.random.exponential(96/c_ij)
        latency = rho + (size/c_ij) + d_ij
        return latency / 1000

    def broadcast(self, tx):
        if tx not in self.queue:
            print("Transaction ", tx, " received by ", self.id, "at", time.perf_counter() - start)
            self.queue[tx]
            for peer in self.connections : 
                latency = self.get_latency(peer, size_of_transaction)
                print("Transaction ", tx, "from ", self.id, " to ", peer.id, "with delay ", latency, "at", time.perf_counter() - start)
                scheduler.add_event(latency, 1, peer.broadcast , (tx,) )
    
    def __str__(self) -> str:
        return str(self.id)


Network = generate_random_connected_graph(N)
for i in range(N):
    Peer(i not in peers_slow, i not in peers_low_cpu)

for node in Network.nodes():
    peers[node].connections = [peers[i] for i in Network.neighbors(node)]


env = simpy.rt.RealtimeEnvironment(factor=1)
for p in peers:
    env.process(p.generate(env))

env.run(until=10)


scheduler_thread.join()