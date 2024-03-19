import networkx as nx
import random

def generate_random_connected_graph(num_nodes, min_connections=3, max_connections=6):
    """ For each node , start adding random nodes as it neigbhours with 
    given min and max connections . If the graph doesnt form a connected graph ,
    then the while loop continues until it finds a connected graph"""
    while True:
        graph = nx.Graph()
        graph.add_nodes_from(range(num_nodes))

        for node in graph.nodes():
            existing_connections = graph.degree(node)
            num_connections = random.randint(min_connections, max_connections) - existing_connections
            num_connections = max(num_connections, 0)

            possible_peers = set(graph.nodes()) - {node} - set(graph.neighbors(node))
            possible_peers = [i for i in possible_peers if graph.degree(i) < max_connections]
            
            if len(possible_peers) < num_connections:
                break

            random_peers = random.sample(possible_peers, num_connections)
            graph.add_edges_from([(node, peer) for peer in random_peers])

        if nx.is_connected(graph):
            return graph


