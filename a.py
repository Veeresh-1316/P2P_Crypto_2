import time, hashlib
start = time.perf_counter()
size_of_transaction = 8
from copy import deepcopy

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
        return f"block : {self.blkid}, {self.miner_id}"
    
    def prevblkid(self):
        return self.prev_blkid
    
def temp(block):
    print("IN")
    l = deepcopy(block)
    print("OUT")

    dic[l.blkid] = l

GENESIS_BLOCK = Block(-1, time.time() - start, [], -1)
dic = {GENESIS_BLOCK.blkid : GENESIS_BLOCK}

t = Block(GENESIS_BLOCK.blkid, time.time() - start, [], -1)
k = deepcopy(t)

print("before")
temp(k)
print("after")

l = deepcopy(k)
temp(l)
dic[l.blkid] = l
print("after")

print(GENESIS_BLOCK)
print(t)
print(k)
print(dic)

d = deepcopy(dic)
print(d)

# import asyncio
# from copy import copy
# import random

# def v(i, var):
#     print(i,":", var)

# async def temp(var, i):
#     l = copy(var)

#     while(True):
#         t = random.uniform(0, 5)
#         await asyncio.sleep(t)
#         v(i, var)


# lis = []
# for i in range(50):
#     lis.append(Block(-1, time.time() - start, [], i))

# async def main():
#     tasks = []
#     for i in range(50):
#         tasks.append(asyncio.create_task (temp(lis[i], i)))
#     await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)


# asyncio.run(main())