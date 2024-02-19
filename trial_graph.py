from graphviz import Digraph
from start import Block

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

Blocks = []

g = GenPlot(Blocks)
g.render("Blockchain", format="png")