from collections import defaultdict
import hashlib
from multiprocessing import Pool
from multiprocessing import pool
from multiprocessing.pool import ThreadPool
import random
import numpy as np
import simpy
import time
import graph
from threading import Thread

interarrival_mean_time = 5
coins_per_transaction = 1
size_of_transaction = 1024*8    # bits
N = 50
z0 = 0.5
z1 = 0.5
rho_ij = np.random.randint(10, 500)     # ms - light propagation delay

peers = []
peers_slow = np.random.choice(N, int(z0*N), replace=False)
peers_low_cpu = np.random.choice(N, int(z1*N), replace=False)

start = time.time()

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
            print("Generating by ", self.id, "at ", time.time() - start)
            print(tx)
            thread = Thread(target=self.broadcast, args=(tx,))
            thread.start()

    def broadcast(self, tx):
        if tx not in self.queue:
            print("Transaction ", tx, " received by ", self.id)
            self.queue[tx]

            pool = ThreadPool(processes=10)
            def wait_brod(peer,tx,latency) : 
                time.sleep(latency)
                peer.broadcast(tx)
            for result in pool.starmap( wait_brod ,  ((peer,tx, random.randint(2,5) )for peer in self.connections) )  : pass 



    
    def __str__(self) -> str:
        return str(self.id)


Network = graph.generate_random_connected_graph(N)
for i in range(N):
    Peer(i not in peers_slow, i not in peers_low_cpu)

for node in Network.nodes():
    peers[node].connections = [peers[i] for i in Network.neighbors(node)]


env = simpy.rt.RealtimeEnvironment(factor=1)
for p in peers:
    env.process(p.generate(env))

env.run(until=5)


