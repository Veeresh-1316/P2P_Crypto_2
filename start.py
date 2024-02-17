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

block_publisher = PriorityQueueScheduler()
block_publisher_thread = Thread(target=block_publisher.run)
block_publisher_thread.start()


interarrival_mean_time = 9
coins_per_transaction = 1
size_of_transaction = 8    # kilo-bits
max_transactions_per_block = 1000

N = 5
z0 = 0.5
num_slow = int(z0*N)
z1 = 0.5
num_low_cpu = int(z1*N)
rho = random.random()*490 + 10     # ms - light propagation delay

peers = []
peers_slow = np.random.choice(N, num_slow, replace=False)
peers_low_cpu = np.random.choice(N, num_low_cpu, replace=False)
slow_hash_power = 1/(10*N - 9*num_low_cpu)
hash_ratio = {True: 10, False: 1}

start = time.perf_counter()

# all_transactions = []

class Transaction:
    def __init__(self, sender, receiver, coins):
        self.timestamp = time.perf_counter()
        self.txid = hashlib.md5((str(random.randint(1,100))+str(self.timestamp)).encode('utf-8')).hexdigest()
        self.sender = sender
        self.receiver = receiver
        self.coins = coins
        
    def __hash__(self) -> int:
        return hash(self.txid) 
    
    def __repr__(self):
        #TxnID: IDx pays IDy C coins
        return f"{self.txid}: {self.sender} pays {self.receiver} {self.coins} coins"

class CoinBaseTransaction(Transaction) : 
      def __init__(self, miner):
          super().__init__(None, miner, 50)

      def __repr__(self):
          return f"{self.txid}: {self.receiver} mines {self.coins} coins"
      
class Block:
    def __init__(self, prev_blkid, creationTime, transactions):
        self.prev_blkid = prev_blkid
        self.creation_time = creationTime
        self.transactions = transactions
        self.blkid = hashlib.md5(str([self.prev_blkid, self.creation_time, [str(i) for i in self.transactions]]).encode()).hexdigest()

    def size(self):
        return len(self.transactions) * size_of_transaction

    def __hash__(self):
        return hash(self.blkid)

    def prevblkid(self):
        return self.prev_blkid

GENESIS_BLOCK = Block(0, time.time() - start, [])

class BlockChain:
    def __init__(self):
        self.GENESIS_BLOCK = GENESIS_BLOCK
        self.blocks_all = {GENESIS_BLOCK.blkid: GENESIS_BLOCK}
        self.unadded_blocks = []

        self.all_transactions = set()  ## all transactions in all blockchain
        self.txn_pool = set()       ## all transactions in longest chain

        self.depth = {GENESIS_BLOCK.blkid: 0}
        self.balances =  { GENESIS_BLOCK.blkid: np.zeros(N) }
        
        self.longest_length = 0
        self.longest_block = GENESIS_BLOCK

    def get_last_block(self):
        return self.longest_block

    def is_valid(self, block):
        parent_balances = self.balances[block.prev_blkid]
        new_balance = np.copy(parent_balances)
        transactions = block.transactions
        valid = True

        if transactions[0].sender is None:
            new_balance[receiver.id] += transactions[0].coins
            transactions = transactions[1:]

        for t in transactions:
            sender = t.sender
            receiver = t.receievr
            coins = t.coins
            if new_balance[sender.id] >= coins:
                new_balance[sender.id]   -= coins
                new_balance[receiver.id] += coins
            else:
                valid = False
                break
        return valid, new_balance
    
    def change_mining_branch(self, new_longest_blkid):
        old_longest_blkid = self.longest_block.blkid
        old_depth = self.depth[old_longest_blkid]
        new_depth = self.depth[new_longest_blkid]
        min_depth = min(old_depth, new_depth)

        ancestor_old = old_longest_blkid
        ancestor_new = new_longest_blkid

        while min_depth < self.depth[ancestor_old]:
            self.txn_pool = self.txn_pool - set(self.blocks_all[ancestor_old].transactions)
            ancestor_old = self.blocks_all[ancestor_old].prev_blkid
        while min_depth < self.depth[ancestor_new]:
            self.txn_pool = self.txn_pool + set(self.blocks_all[ancestor_new].transactions)
            ancestor_new = self.blocks_all[ancestor_new].prev_blkid
        while ancestor_old != ancestor_new:
            self.txn_pool = self.txn_pool - set(self.blocks_all[ancestor_old].transactions)
            self.txn_pool = self.txn_pool + set(self.blocks_all[ancestor_new].transactions)
            ancestor_old = self.blocks_all[ancestor_old].prev_blkid
            ancestor_new = self.blocks_all[ancestor_new].prev_blkid

    def pop_blocks_with_parent(self, block):
        invalid_blocks = []
        for i in self.unadded_blocks:
            if i.prev_blkid == block.blkid:
                invalid_blocks.append(i)
        for i in invalid_blocks:
            self.pop_blocks_with_parent(i)
            self.unadded_blocks.remove(i)

    def check_and_add_unadded(self, block):
        added_blocks = []
        invalid_blocks = []
        length = self.depth[block.blkid]
        blk = block

        for i in self.unadded_blocks:
            if i.prev_blkid == block.blkid:
                # VALIDATE
                # ADD THIS NEW BLOCK TO BLOCKCHAIN

                valid, new_balance = self.is_valid(block)
            
                if not valid:
                    invalid_blocks.append(i)
                
                self.balances[i.blkid] = np.copy(new_balance)
                self.blocks_all[i.blkid] = block
                self.depth[i.blkid] = self.depth[block.blkid] + 1

                for t in i.transactions:
                    self.all_transactions.insert(t)

                # AND CHECK AGAIN FOR UNADDED_BLOCKS WITH THIS AS PARENT
                added_blocks.append(i)
        
        for i in invalid_blocks:
            self.pop_blocks_with_parent(i)
            self.unadded_blocks.remove(i)

        for i in added_blocks:
            (new_length, new_block) = self.check_and_add_unadded(i)
            if new_length > length:
                length = new_length
                blk = new_block
        
        return length, blk

    def add_block(self, block):
        parent_id = block.prev_blkid
        blkid = block.blkid

        if blkid in self.blocks_all:
            return False

        if parent_id not in self.blocks_all:
            self.unadded_blocks.append(block)
        else:
            valid, new_balance = self.is_valid(block)
            
            if not valid:
                return False
            
            self.balances[blkid] = np.copy(new_balance)
            self.blocks_all[blkid] = block
            self.depth[blkid] = self.depth[parent_id] + 1

            (new_length, new_block) = self.check_and_add_unadded(block)
            for t in block.transactions:
                self.all_transactions.insert(t)

            if (new_length > self.longest_length):
                self.change_mining_branch(new_block.blkid)
                self.longest_length = new_length
                self.longest_block = new_block
                return True     ## create new block
            else:
                return False

class Peer:
    def __init__(self, speed, cpu):
        self.speed = speed
        self.cpu = cpu
        self.id = len(peers)
        peers.append(self)
        self.bitcoins = 0
        self.transactions = []
        self.recieved_blocks = set()
        self.recieved_transactions = set()
        self.connections = []
        self.hash_power = slow_hash_power * hash_ratio[cpu]
        ### start mining 
        self.create_and_publish_block()

         
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

    def broadcast(self, msg):
        queue = self.recieved_transactions if isinstance(msg,Transaction) else self.recieved_blocks
        if msg not in queue:
               queue.add(msg)
               for peer in self.connections : 
                   latency = self.get_latency(peer, size_of_transaction)
                   print(f"{type(msg)} ", msg , "from ", self.id, " to ", peer.id, "with delay ", latency, "at", time.perf_counter() - start)
                   scheduler.add_event(latency, peer.broadcast , (msg,) )

        if isinstance(msg,Block) : 
           block = msg 
           if self.blockchain.add_block(block) : self.create_and_publish_block()
    
    def create_and_publish_block(self) : 
        unpublished_transaction = self.broadcast_transaction_set - set(self.blockchain.txn_pool)
        no_of_tranasctions = min(unpublished_transaction,random.randint(0,max_transactions_per_block -1))
        coinbase_transaction = CoinBaseTransaction(self) 
        transactions = [coinbase_transaction] + list( random.sample(unpublished_transaction,no_of_tranasctions) )
        tk = np.random.exponential( interarrival_mean_time / self.hash_power )
        block = Block( self.blockchain.get_last_block().blkid , time.time() + tk , transactions )
        self.publish_block( block , tk )

    def publish_block(self,block:Block,tk) : 
        def temp_publish_block(peer,block:Block) : 
            if block.prev_blkid == peer.blockchain.get_last_block().blkid : 
               peer.brodcast(block)
            else : print(f"block aborted :: {block} by peer :: {peer} due to new chain")
        block_publisher.add_event(tk, temp_publish_block, (self,block))
        
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





def GenPlot(Blocks):

    g = Digraph('blockchain', node_attr={'shape': 'record', 'style': 'rounded,filled', 'fontname': 'Arial'})
    g.graph_attr['rankdir'] = 'RL'

    genesis_block_id = GenB.blkid
    depth = 10
    for key in Blocks:
        block = Blocks[key]
        block_label = f'<hash> Hash={str(block.blkid)[:7]} ' \
                    f'|<link> Link={str(block.prev_blkid)[:7]} ' \
                    f'| MineTime={block.creation_time:.1f}' \
                    f'| {{Idx={depth} | Miner={block.miner_id}}}' \
                    f'| {{NewTxnIncluded={len(block.transactions) - (block.miner_id != "?")}}}'
        g.node(name=key, label=block_label)

    for key in Blocks:
        if key != genesis_block_id:
            block = Blocks[key]
            g.edge(tail_name=f'{block.blkid}', head_name=f'{block.prev_blkid}')

    return g

g = GenPlot(Blocks)
g.render("Blockchain", format="png")