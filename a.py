from threading import Thread
from scheduler import PriorityQueueScheduler
block_publisher = PriorityQueueScheduler()
block_publisher_thread = Thread(target=block_publisher.run)
block_publisher_thread.start()

def publish_block(peer,block,delay) :
    def temp_publish_block(peer,block) : 
        if block.get_previous_block() == peer.blockchain.get_last_block() : 
           peer.brodcast(block)
        else : print(f"block aborted :: {block} by peer :: {peer} due to new chain")
    block_publisher.add_event(delay, temp_publish_block, (peer,block))

