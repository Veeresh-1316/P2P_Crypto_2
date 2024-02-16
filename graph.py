import networkx as nx
import random

def generate_random_connected_graph(num_nodes, min_connections=3, max_connections=6):
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

# # Set the number of peers
# num_peers = 10

# # Generate a random connected graph
# random_connected_graph = generate_random_connected_graph(num_peers)

# # Print the edges of the graph
# print("Edges of the Random Connected Graph:")
# print(random_connected_graph.edges())

# # You can visualize the graph using networkx
# nx.draw(random_connected_graph, with_labels=True)
