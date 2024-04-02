import argparse
import asyncio
import hashlib
import logging
import random
from graphviz import Digraph
import numpy as np
from copy import copy
import time
from graph import generate_graph
import os 

os.makedirs("peers",exist_ok=True)
os.makedirs("fig",exist_ok=True)

## Argparser 
parser = argparse.ArgumentParser(prog='Discrete P2P Simulator')
parser.add_argument('h1',type=float,help="Hash power of first adversary")
parser.add_argument('h2',type=float,help="Hash power of second adversary")
args = parser.parse_args()

### Tunable paramters 
N = 28  # no. of honest miners
interarrival_mean_time = 0.5
interarrival_mean_block_time = 2
size_of_transaction = 8    # kilo-bits
max_transactions_per_block = 1000
COINBASE_COINS_PER_TRANSACTION = 50

transaction_simulation_time = 70 # time to generate transaction 
full_simulation_time = 100 # Full time to end program 
h1 = args.h1 # between 0 and 1 
h2 = args.h2 # between 0 and 1
### End tunable parameters

# 50% of honest nodes have slow network
# both selfish miners have fast network
num_slow = int(N//2)
rho = random.random()*490 + 10     # ms - light propagation delay

peers = []
peers_slow = np.random.choice(N, num_slow, replace=False)

# all honest miners have equal hashing power
honest_hash_power = (1-h1-h2)/N
attack_hash_power = [h1, h2]

start = time.perf_counter()


class Transaction :
    # A class to represent transaction with sender , reciever and coins of the transaction 
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

    def size(self):
        return size_of_transaction

class CoinBaseTransaction(Transaction) :
      # A special subclass of transaction where the sender is None and coins = 50 
      def __init__(self, miner):
          super().__init__(None, miner, COINBASE_COINS_PER_TRANSACTION)

      def __repr__(self):
          return f"{self.txid}: {self.receiver} mines {self.coins} coins"

class Block :
    # A class reprensenting blocks having the neccesary attributes (prev_blk_id,blk_id,createtime,transactions,miner)
    def __init__(self, prev_blkid, creationTime, transactions, miner_id):
        self.prev_blkid = prev_blkid
        self.creation_time = creationTime - start
        self.transactions = transactions
        self.blkid = hashlib.md5(str([self.prev_blkid, self.creation_time, [str(i) for i in self.transactions]]).encode()).hexdigest()
        self.miner_id = miner_id 

    def size(self):
        return len(self.transactions) * size_of_transaction
    
    #Function to store a block in a set / dictionary (needs to be hashable)
    def __hash__(self):
        return hash(self.blkid)
    
    #Repr of a block object in print : block : blk_id 
    def __repr__(self) -> str:
        return f"block : {self.blkid}"
    
    def prevblkid(self):
        return self.prev_blkid

GENESIS_BLOCK = Block(-1, time.time() - start, [],-1)
INTIAL_BALANCES = np.random.randint(50,size=N+2) 

## Blockchain class representing the blockchain data stored in a peer
class BlockChain :
    
    def __init__(self, peer):
        self.GENESIS_BLOCK = GENESIS_BLOCK
        self.blocks_all = {GENESIS_BLOCK.blkid: GENESIS_BLOCK}
        self.unadded_blocks = set()

        self.all_transactions = set()  ## all transactions in all blockchain
        self.txn_pool = set()       ## all transactions in longest chain

        self.depth = {GENESIS_BLOCK.blkid: 0}
        self.balances =  { GENESIS_BLOCK.blkid:  INTIAL_BALANCES}

        self.longest_length = 0
        self.longest_block = GENESIS_BLOCK
        
        # THIS IS PER PEER BASIS ###########
        self.peer = peer 
        self.blocks_in_longest_chain = 0            # num_blocks in longest chain for peer i
        self.total_blocks_generated = 0             # total num_blocks generated by peer i
        ####################################
    
    #Get the last block of the longest chain of the blockchain 
    def get_last_block(self):
        return self.longest_block
    
    #Check if a block recieved through broadcast is valid 
    def is_valid(self, block:Block):
        parent_balances = self.balances[block.prev_blkid]
        new_balance = np.copy(parent_balances)
        transactions: list[Transaction] = block.transactions 
        valid = True

        if len(transactions) == 0:
            return valid, new_balance

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
                self.peer.logger.info(f"Rejected {block} due to transaction : {t}")
                valid = False
                break
        
        return valid, new_balance
    
    #Change Mining branch / longest branch in the block chain due to the new_longest_block
    def change_mining_branch(self, new_longest_blkid):
        old_longest_blkid = self.longest_block.blkid
        old_depth = self.depth[old_longest_blkid]
        new_depth = self.depth[new_longest_blkid]
        min_depth = min(old_depth, new_depth)

        ancestor_old = old_longest_blkid
        ancestor_new = new_longest_blkid

        while min_depth < self.depth[ancestor_old]:
            if(self.blocks_all[ancestor_old].miner_id == self.peer.id) :
                self.blocks_in_longest_chain -= 1
            self.txn_pool = self.txn_pool - set(self.blocks_all[ancestor_old].transactions)
            ancestor_old = self.blocks_all[ancestor_old].prev_blkid
        while min_depth < self.depth[ancestor_new]:
            if(self.blocks_all[ancestor_new].miner_id == self.peer.id) :
                self.blocks_in_longest_chain += 1
            self.txn_pool = self.txn_pool | set(self.blocks_all[ancestor_new].transactions)
            ancestor_new = self.blocks_all[ancestor_new].prev_blkid
        while ancestor_old != ancestor_new:
            if(self.blocks_all[ancestor_old].miner_id == self.peer.id) :
                self.blocks_in_longest_chain -= 1
            if(self.blocks_all[ancestor_new].miner_id == self.peer.id) :
                self.blocks_in_longest_chain += 1

            self.txn_pool = self.txn_pool - set(self.blocks_all[ancestor_old].transactions)
            self.txn_pool = self.txn_pool | set(self.blocks_all[ancestor_new].transactions)
            ancestor_old = self.blocks_all[ancestor_old].prev_blkid
            ancestor_new = self.blocks_all[ancestor_new].prev_blkid
    
    def pop_blocks_with_parent(self, block:Block):
        invalid_blocks = []
        for i in self.unadded_blocks:
            if i.prev_blkid == block.blkid:
                invalid_blocks.append(i)
        for i in invalid_blocks:
            self.pop_blocks_with_parent(i)
            self.unadded_blocks.remove(i)

    def check_and_add_unadded(self, block:Block):
        added_blocks = []
        invalid_blocks = []
        length = self.depth[block.blkid]
        blk = block

        for i in self.unadded_blocks:
            if i.prev_blkid == blk.blkid:
                # VALIDATE
                # ADD THIS NEW BLOCK TO BLOCKCHAIN

                valid, new_balance = self.is_valid(i)

                if not valid:
                    invalid_blocks.append(i)

                self.balances[i.blkid] = np.copy(new_balance)
                self.blocks_all[i.blkid] = i
                self.depth[i.blkid] = self.depth[blk.blkid] + 1
                
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
    
    #Add a block to the blockchain if valid and return if the block creates a new longest chain 
    def add_block(self, block:Block):
        parent_id = block.prev_blkid
        blkid = block.blkid
        blk = block

        if blkid in self.blocks_all:
            return False

        if parent_id not in self.blocks_all:
            self.unadded_blocks.add(block)
        else:
            valid, new_balance = self.is_valid(block)

            if not valid:
                return False

            self.balances[blkid] = np.copy(new_balance)
            self.blocks_all[blkid] = block
            self.depth[blkid] = self.depth[parent_id] + 1

            (new_length, new_block) = self.check_and_add_unadded(block)
            # print("4: ", blk, block)

            self.peer.logger.info(f"Adding block {block} at time {time.time()}")
            for t in block.transactions:
                self.all_transactions.add(t)

            if (new_length > self.longest_length):
                self.change_mining_branch(new_block.blkid)
                self.longest_length = new_length
                self.longest_block = new_block
                return True     ## create new block
            else:
                return False
   
    def get_MPU_ratio(self, p):
        if p == -1:
            return (self.longest_length + 1) / len(self.blocks_all)
        
        peer_count = 0
        total_count = 0
        node = self.longest_block

        while node != GENESIS_BLOCK:
            if node.miner_id == p:
                peer_count += 1
            total_count += 1
            node = self.blocks_all[node.prev_blkid]

        total_count += 1 # to count GENESIS BLOCK
        return peer_count/total_count


class Peer :
    ### One peer object / peer in network (speed & cpu) . 
    ### Its activity is logged in peer/peer_{id}.txt 
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
        self.blockchain = BlockChain(self)  # It has a blockchain object which maintains its blockchain data 
        if cpu:
            self.hash_power = honest_hash_power
        else:
            self.hash_power = attack_hash_power[self.id - N]
        
        self.logger = logging.getLogger(f"peer_{self.id}")  # Logger 
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(f"peers/peer_{self.id}.txt",mode='w+')
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    # Function to generate transactions 
    async def generate(self):
        while True:
            tim = np.random.exponential(interarrival_mean_time) 
            await asyncio.sleep(tim)
            current_bal = self.blockchain.balances[self.blockchain.longest_block.blkid][self.id]
            coins_per_transaction = round( random.uniform(0.01,current_bal/10) , 2  )
            # Create a transaction from current peer to a random peer with valid coins . 
            tx = Transaction(self, random.choice(peers[:self.id]+peers[self.id+1:]), coins_per_transaction) #Transaction object
            self.transactions.append(tx)
            self.logger.info(f"Generating Transaction {tx}")
            asyncio.create_task( self.broadcast((tx)) )

    def get_latency(self, peer, size): # Latency of network connection link between two peers 
        c_ij = 100 if (self.speed and peer.speed) else 5
        d_ij = np.random.exponential(96/c_ij)
        latency = rho + (size/c_ij) + d_ij
        latency = latency #expriment *50
        return latency / 1000
    
    # Function to both recieve and brodcast to neighbour clients (both block and transactions)
    async def broadcast(self, msg , delay = 0 ):
        queue = self.recieved_transactions if isinstance(msg,Transaction) else self.recieved_blocks
        await asyncio.sleep(delay) 
        ### Loopless implementation of brodcasting in network 
        # if is msg is already recieved , it is stored in the queue . the next time it will be ignored 
        # else , Add the msg in queue . Do appropiate action 
        if msg not in queue:
               queue.add(msg)
               self.logger.info(f"Recieved {msg}")
               tasks = []
               for peer in self.connections :
                   latency = self.get_latency(peer, msg.size())
                   self.logger.info(f"Sending {msg} , at latency : {latency} , to : {peer}")
                   tasks.append( peer.broadcast(msg , latency) )

               if isinstance(msg,Block) :
                   block = msg
                   if self.blockchain.add_block(block) :  # This function returns if it creates a new long chain 
                        tasks.append( self.create_and_publish_block() ) # Create a block and add to publish thread 
                   else : 
                       self.logger.info(f"Invalid / Non Longest Chain Block {msg}")
               await asyncio.gather(*tasks)

    ### Check if a transaction is valid , by using the balances of the peer from the blockchain 
    def valid_transactions(self, transactions:list[Transaction],n):
        ## should not include coinbase
        ## all chosen transactions should be valid according to last longest block
        final_transactions = set()
        temp_bal = np.copy(self.blockchain.balances[ self.blockchain.longest_block.blkid ])
        for i in transactions : 
            if i.sender is None : continue 
            sender , reciever , coins = i.sender.id , i.receiver.id , i.coins 
            if temp_bal[sender] >= coins : 
                temp_bal[sender] -= coins 
                temp_bal[reciever] += coins
                final_transactions.add(i) 
            if len(final_transactions) == n : return final_transactions 
        return final_transactions 
            
    ### Creates a block object immediatly using a set of valid & unpublished transaction . Then call the publish 
    ### function which publish the block after a delay . 
    async def create_and_publish_block(self) :
        #Get a list of valid transaction , that are not in longest chain 

        unpublished_transaction = (self.recieved_transactions | self.blockchain.all_transactions) - self.blockchain.txn_pool
        no_of_tranasctions = min( len(unpublished_transaction) ,random.randint(0,max_transactions_per_block -1))
        valid_transaction = self.valid_transactions(unpublished_transaction,no_of_tranasctions)
        coinbase_transaction = CoinBaseTransaction(self) # Add coinbase transaction 
        transactions = [coinbase_transaction] + list(valid_transaction)
        tk = np.random.exponential( interarrival_mean_block_time / self.hash_power ) # random exponentional block publishing time 
        block = Block( self.blockchain.get_last_block().blkid , time.time() + tk , transactions , self.id )
        self.logger.info(f"Created {block} , publish at : {tk}")

        await asyncio.sleep(tk)
        if block.prev_blkid == self.blockchain.get_last_block().blkid :
               self.logger.info(f"{self} is publishing block : {block}")
               self.blockchain.total_blocks_generated += 1
               await asyncio.create_task(self.broadcast(block))
        else : # Abort as longest chain changed 
                self.logger.info(f"block aborted :: {block} by peer :: {self} due to new chain")


    # Print blockchain as .png in fig/ folder 
    def print_blockchain(self):
        print(self.id)
        print("Total: ", self.blockchain.total_blocks_generated)
        print("Longest: ", self.blockchain.blocks_in_longest_chain)
        g = Digraph('blockchain', node_attr={'shape': 'record', 'style': 'rounded,filled', 'fontname': 'Arial'})
        g.graph_attr['rankdir'] = 'RL'
    
        genesis_block_id = GENESIS_BLOCK.blkid
        Blocks = copy(self.blockchain.blocks_all)

        longest_chain = set()
        node = self.blockchain.longest_block.blkid
        while node != GENESIS_BLOCK.blkid:
            longest_chain.add(node)
            node = Blocks[node].prev_blkid

        for key in Blocks :
            block = Blocks[key]
            block_label = f'<hash> Hash={str(block.blkid)[:7]} ' \
                        f'|<link> Link={str(block.prev_blkid)[:7]} ' \
                        f'| MineTime={block.creation_time:.1f}' \
                        f'| {{Idx={self.blockchain.depth[ key ]} | Miner={block.miner_id}}}' \
                        f'| {{NewTxnIncluded={ len(block.transactions)  }}}'
            self.logger.info(f"graph :: {key}")

            # HONEST BLOCKS  : lightgrey color
            # SELFISH MINER 1: lightblue color
            # SELFISH MINER 2: rd color

            if key in longest_chain:    # Add yellow border for longest chain
                if block.miner_id == N :  
                    g.node(name=key, label=block_label, _attributes = {"color":"yellow", "fillcolor":"lightblue"})
                elif block.miner_id == N+1 :  
                    g.node(name=key, label=block_label, _attributes = {"color":"yellow", "fillcolor":"pink"})
                else :
                    g.node(name=key, label=block_label, _attributes = {"color":"yellow", "fillcolor":"lightgrey"})
            else:
                if block.miner_id == N :  
                    g.node(name=key, label=block_label, _attributes = {"fillcolor":"lightblue"})
                elif block.miner_id == N+1 :  
                    g.node(name=key, label=block_label, _attributes = {"fillcolor":"pink"})
                else :
                    g.node(name=key, label=block_label, _attributes = {"fillcolor":"lightgrey"})

        # show number of unpublished blocks for adversary
        if self.id == N:
            if(len(self.private_queue) > 0):
                g.node(name="MORE", label=f'+{len(self.private_queue)}', _attributes = {"color":"lightblue", "fillcolor":"white"})
                g.edge(tail_name=f'MORE', head_name=f'{self.private_queue[0].prev_blkid}')
        elif self.id == N+1:
            if(len(self.private_queue) > 0):
                g.node(name="MORE", label=f'+{len(self.private_queue)}', _attributes = {"color":"red", "fillcolor":"white"})
                g.edge(tail_name=f'MORE', head_name=f'{self.private_queue[0].prev_blkid}')
    
        for key in Blocks:
            if key != genesis_block_id:
                block = Blocks[key]
                g.edge(tail_name=f'{block.blkid}', head_name=f'{block.prev_blkid}')
        g.render(filename = f"blockchain_{self.id}.png", directory = "fig/",view=False)

    def __str__(self) -> str:
        return str(self.id)

# SELFISH MINER sub-classed from PEER
class Selfish_Miner(Peer):
    def __init__(self, speed, cpu):
        super().__init__(speed, cpu)
        self.private_lead = 0
        self.private_longest_block = GENESIS_BLOCK  # the block on which the selfish miner mines
        self.private_queue = list()                 # list of unpublished private blocks
    
    # selfish miner does not generate transactions (no use of wasting time on this)
    async def generate(self):
        pass

    # selfish miner broadcast function (broadcast after 'delay' time -- includes queuing delay and transmission delay form previous peer)
    async def broadcast(self, msg , delay = 0 ):
        if(isinstance(msg, Transaction)):   # don't forward transactions
            return
        if(msg.miner_id == self):           # don't forward self-generated blocks
            return

        await asyncio.sleep(delay)  # to mimic delay
        
        ### Loopless implementation of brodcasting in network
        if msg in self.recieved_blocks:
            return
        
        self.logger.info(f"Recieved {msg}")
        

        if self.blockchain.add_block(msg) :  # This function returns if it creates a new long chain 
            await self.release_block()
        else : 
            self.logger.info(f"Invalid / Non Longest Chain Block {msg}")


    # send the list of blocks (from private queue) to the neighbours after adding to self blockchain
    async def send_blocks(self, blocks):
        for block in blocks:
            self.blockchain.add_block(block)
            for peer in self.connections :
                latency = self.get_latency(peer, block.size())
                self.logger.info(f"Sending {block} , at latency : {latency} , to : {peer}")
                asyncio.create_task(peer.broadcast(block, latency))

    # this function is called when the lead over private chain changes
    # i.e. when a new public block is added to longest chain
    async def release_block(self) :
        self.logger.info(f"Entered release_block")

        # if there is nothing in private queue
        # the simply mine on the new longest chain (which is public)
        if len(self.private_queue) == 0:
            self.private_longest_block = self.blockchain.longest_block
            self.private_lead = 0
            asyncio.create_task( self.mine_privately() )
            return 


        # lvc - length of public chain from point of unpublished blocks
        lvc = self.blockchain.longest_length - self.blockchain.depth[self.private_queue[0].prev_blkid]
        # pvc - length of private chain from point of unpublished blocks
        pvc = len(self.private_queue)

        # the lead of the private chain over public chain
        lead = pvc - lvc         
        self.logger.info(f"Lead = {lead}")

        # if new_lead is < 0  => public chain ahead
        # discard private blocks and mine on new public longest chain
        if lead < 0:
            self.private_lead = 0
            self.private_longest_block = self.blockchain.longest_block
            self.private_queue = []
            asyncio.create_task( self.mine_privately() ) 
        
        # if lead is 0 or 1
        # publish all private blocks, and continue mining on same private chain
        elif lead == 0 or lead == 1:
            asyncio.create_task(self.send_blocks(self.private_queue))
            self.private_queue = []
            self.private_lead = lead
        
        # if lead is >= 2
        # just release one of the private blocks and continue mining on same private chain
        else:
            asyncio.create_task(self.send_blocks(self.private_queue[:1]))
            self.private_queue = self.private_queue[1:]
            self.private_lead = lead

    # Selfish miner user another functions mine_privately() to mine blocks
    # since there is no publish involved as soon as mine done
    async def create_and_publish_block(self):
        return await self.mine_privately()
    
    # mine block on private chain
    async def mine_privately(self) :

        coinbase_transaction = [ CoinBaseTransaction(self) ] # Add coinbase transaction
        tk = np.random.exponential( interarrival_mean_block_time / self.hash_power ) # random exponentional block publishing time 
        block = Block( self.private_longest_block.blkid , time.time() + tk , coinbase_transaction , self.id )
        self.logger.info(f"Created {block} , publish at : {tk}")

        # mimic block creation time
        await asyncio.sleep(tk)

        # if block still valid, i.e. private chain not disturbed
        if block.prev_blkid == self.private_longest_block.blkid:
            # add to private_queue and mine again
            self.blockchain.total_blocks_generated += 1
            self.private_queue.append(block)
            self.private_longest_block = block
            asyncio.create_task(self.mine_privately())

        else : # Abort as private queue disturbed
            self.logger.info(f"block aborted :: {block} by peer :: {self} due to new chain")



### Create a connected graph of peers with given min and max connections / peer . 
Network = generate_graph(N+2)

# N honest miners
for i in range(N):
    Peer(i not in peers_slow, True)

# 2 independent selfish miners
Selfish_Miner(True, False)
Selfish_Miner(True, False)

for node in Network.nodes():
    peers[node].connections = [peers[i] for i in Network.neighbors(node)]
### Network creation of peer ends 

# THREAD which prints results or ends simulation as and when requested by user
# async def input_thread() : 
#     i = await asyncio.to_thread(input, "Press p to print & e to exit :")
#     while True : 
#         for peer in peers : 
#             peer.print_blockchain() ## Print it to a file
        
#         # pick a random honest node and find MPU ratios
#         mpu_index = random.randint(0, N-1)
#         mpu_0 = peers[mpu_index].blockchain.get_MPU_ratio(-1)
#         mpu_1 = peers[mpu_index].blockchain.get_MPU_ratio(N)
#         mpu_2 = peers[mpu_index].blockchain.get_MPU_ratio(N+1)

#         print(f'MPU_{mpu_index}_overall = {mpu_0}')
#         print(f'MPU_{mpu_index}_adv1 = {mpu_1}')
#         print(f'MPU_{mpu_index}_adv2 = {mpu_2}')

#         if i == "e" : break 
#         i = await asyncio.to_thread(input, "Press p to print & e to exit :")
#     import os 
#     os._exit(0)

async def input_thread() :
    await asyncio.sleep(full_simulation_time)

    for peer in peers : 
        peer.print_blockchain() ## Print it to a file
    
    # pick a random honest node and find MPU ratios
    mpu_index = random.randint(0, N-1)
    mpu_0 = peers[mpu_index].blockchain.get_MPU_ratio(-1)
    mpu_1 = peers[mpu_index].blockchain.get_MPU_ratio(N)
    mpu_2 = peers[mpu_index].blockchain.get_MPU_ratio(N+1)

    print(f'MPU_{mpu_index}_overall = {mpu_0}')
    print(f'MPU_{mpu_index}_adv1 = {mpu_1}')
    print(f'MPU_{mpu_index}_adv2 = {mpu_2}')

    import os 
    os._exit(0)

async def main() :
    publish_block = tuple( (peer.create_and_publish_block() for peer in peers) )
    generate_txns = tuple( (peer.generate() for peer in peers) )
    await asyncio.gather( input_thread() , *publish_block , *generate_txns )

asyncio.run(main())
