from collections import defaultdict
import hashlib
import logging
from multiprocessing import Pool
from multiprocessing import pool
from multiprocessing.pool import ThreadPool
import random
from matplotlib import pyplot as plt
from networkx import DiGraph
import numpy as np
import simpy
import time
from graph import generate_random_connected_graph
from threading import Thread
from scheduler import PriorityQueueScheduler, PriorityQueueScheduler1

scheduler = PriorityQueueScheduler()
scheduler_thread = Thread(target=scheduler.run)
scheduler_thread.start()

block_publisher = PriorityQueueScheduler1()
block_publisher_thread = Thread(target=block_publisher.run)
block_publisher_thread.start()


interarrival_mean_time = 5
interarrival_mean_block_time = 20
coins_per_transaction = 1
size_of_transaction = 8    # kilo-bits
max_transactions_per_block = 1000

N = 8
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
COINBASE_COINS_PER_TRANSACTION = 50

start = time.perf_counter()

###########################
# TO DO: valid_transactions() in PEER class
###########################

class Transaction :
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
          super().__init__(None, miner, COINBASE_COINS_PER_TRANSACTION)

      def __repr__(self):
          return f"{self.txid}: {self.receiver} mines {self.coins} coins"

class Block :

    def __init__(self, prev_blkid, creationTime, transactions,miner_id):
        self.prev_blkid = prev_blkid
        self.creation_time = creationTime
        self.transactions = transactions
        self.blkid = hashlib.md5(str([self.prev_blkid, self.creation_time, [str(i) for i in self.transactions]]).encode()).hexdigest()
        self.miner_id = miner_id 

    def size(self):
        return len(self.transactions) * size_of_transaction

    def __hash__(self):
        return hash(self.blkid)
    
    def __repr__(self) -> str:
        return f"block : {self.blkid}"
    
    def prevblkid(self):
        return self.prev_blkid

GENESIS_BLOCK = Block(-1, time.time() - start, [],-1)

class BlockChain :
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

    def is_valid(self, block:Block):
        parent_balances = self.balances[block.prev_blkid]
        new_balance = np.copy(parent_balances)
        transactions: list[Transaction] = block.transactions 
        valid = True

        if transactions[0].sender is None:
            if transactions[0].coins > COINBASE_COINS_PER_TRANSACTION : 
               return False,new_balance
            new_balance[ transactions[0].receiver.id ] += transactions[0].coins
            transactions = transactions[1:]

        for t in transactions:
            sender = t.sender
            receiver = t.receiver
            coins = t.coins
            if t.sender is None : 
               valid = False 
               break 
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
            self.txn_pool = self.txn_pool | set(self.blocks_all[ancestor_new].transactions)
            ancestor_new = self.blocks_all[ancestor_new].prev_blkid
        while ancestor_old != ancestor_new:
            self.txn_pool = self.txn_pool - set(self.blocks_all[ancestor_old].transactions)
            self.txn_pool = self.txn_pool | set(self.blocks_all[ancestor_new].transactions)
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
                    self.all_transactions.add(t)

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
                self.all_transactions.add(t)

            if (new_length > self.longest_length):
                self.change_mining_branch(new_block.blkid)
                self.longest_length = new_length
                self.longest_block = new_block
                return True     ## create new block
            else:
                return False
    
class Peer :

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
        self.blockchain = BlockChain()
        self.hash_power = slow_hash_power * hash_ratio[cpu]
        
        self.logger = logging.getLogger(f"peer_{self.id}")
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(f"peers/peer_{self.id}.txt",mode='w+')
        file_handler.setLevel(logging.DEBUG)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        self.logger.addHandler(file_handler)

        ### start mining
        self.create_and_publish_block()

    def generate(self, env):
        while True:
            tim = np.random.exponential(interarrival_mean_time)
            yield env.timeout(tim)
            tx = Transaction(self, random.choice(peers[:self.id]+peers[self.id+1:]), coins_per_transaction)
            self.transactions.append(tx)
            self.logger.info(f"Generating Transaction {tx}")
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
               self.logger.info(f"Recieved {msg}")
               for peer in self.connections :
                   latency = self.get_latency(peer, size_of_transaction)
                   self.logger.info(f"Sending {msg} , at latency : {latency} , to : {peer}")
                   #print(f"{type(msg)} ", msg , "from ", self.id, " to ", peer.id, "with delay ", latency, "at", time.perf_counter() - start)
                   scheduler.add_event(latency, peer.broadcast , (msg,) )

               if isinstance(msg,Block) :
                   block = msg
                   if self.blockchain.add_block(block) : self.create_and_publish_block()

    ### TO BE IMPLEMENTED
    def valid_transactions(self, transactions:list[Transaction],n):
        ## should not include coinbase
        ## all chosen transactions should be valid according to last longest block
        final_transactions = set()
        temp_bal = self.blockchain.balances[ self.blockchain.longest_block.blkid ].copy()
        for i in transactions : 
            sender , reciever , coins = i.sender.id , i.receiver.id , i.coins 
            if temp_bal[sender] >= coins : 
                temp_bal[sender] -= coins 
                temp_bal[reciever] += coins
                final_transactions.add(i) 
            if len(final_transactions) == n : return final_transactions 
        return final_transactions 
            
    def create_and_publish_block(self) :
        unpublished_transaction = (self.recieved_transactions | self.blockchain.all_transactions) - self.blockchain.txn_pool
        no_of_tranasctions = min( len(unpublished_transaction) ,random.randint(0,max_transactions_per_block -1))
        valid_transaction = self.valid_transactions(unpublished_transaction,no_of_tranasctions)

        coinbase_transaction = CoinBaseTransaction(self)
        transactions = [coinbase_transaction] + list(valid_transaction)
        tk = np.random.exponential( interarrival_mean_block_time / self.hash_power )
        block = Block( self.blockchain.get_last_block().blkid , time.time() + tk , transactions , self.id )
        self.logger.info(f"Created {block} , publish at : {tk}")
        self.publish_block( block , tk )

    def publish_block(self,block:Block,tk) :
        def temp_publish_block(peer:Peer,block:Block) :
            if block.prev_blkid == peer.blockchain.get_last_block().blkid :
               self.logger.info(f"{peer} is publishing block : {block}")
               peer.broadcast(block)
            else : 
                self.logger.info(f"block aborted :: {block} by peer :: {peer} due to new chain")
                #peer.create_and_publish_block() ## unnecessary 
        block_publisher.add_event(tk, temp_publish_block, (self,block))

    def print_blockchain(self):
        g = DiGraph('blockchain', node_attr={'shape': 'record', 'style': 'rounded,filled', 'fontname': 'Arial'})
        g.graph_attr['rankdir'] = 'RL'
    
        genesis_block_id = GENESIS_BLOCK.blkid
        Blocks = self.blockchain.blocks_all
        for key in Blocks :
            block = Blocks[key]
            block_label = f'<hash> Hash={str(block.blkid)[:7]} ' \
                        f'|<link> Link={str(block.prev_blkid)[:7]} ' \
                        f'| MineTime={block.creation_time:.1f}' \
                        f'| {{Idx={self.blockchain.depth[ key ]} | Miner={block.miner_id}}}' \
                        f'| {{NewTxnIncluded={ len(block.transactions)  }}}'
            g.node(name=key, label=block_label)
    
        for key in Blocks:
            if key != genesis_block_id:
                block = Blocks[key]
                g.edge(tail_name=f'{block.blkid}', head_name=f'{block.prev_blkid}')
        g.view(filename = f"blockchain_{self.id}.png", base_path = "fig/")
        #return g

    def __str__(self) -> str:
        return str(self.id)


Network = generate_random_connected_graph(N)
for i in range(N):
    Peer(i not in peers_slow, i not in peers_low_cpu)

for node in Network.nodes():
    peers[node].connections = [peers[i] for i in Network.neighbors(node)]

# import networkx as nx
# nx.draw_networkx(Network)
# plt.show()

env = simpy.rt.RealtimeEnvironment(factor=1)
for p in peers:
    env.process(p.generate(env))

env.run(until=10)

input("The Input :: ") 
for peer in peers :
    peer.print_blockchain()

scheduler_thread.join()

# g = GenPlot(Blocks)
# g.render("Blockchain", format="png")