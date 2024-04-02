import networkx as nx
import random

# Function to generate a graph with n nodes where each node has degree between 3 and 6
def generate_graph(n):
    if n <= 3:
        print("Viable Graph does not exist")
        import os
        os._exit(1)

    while True:
        invalid = False

        # Create an empty graph
        G = nx.Graph()
        
        # Add n nodes to the graph
        G.add_nodes_from(range(n))
        
        # Ensure each node has a degree between 3 and 6
        for node in G.nodes():
            # Determine the number of edges for the current node (between 3 and 6)
            num_edges = random.randint(3, 6)
            
            # Add edges to the node until it reaches the desired number of edges
            while G.degree(node) < num_edges:
                # Find nodes to connect that are not 'node' and are not already connected to 'node'
                possible = [n for n in range(n) if n != node and not G.has_edge(node, n)]

                # If required numbers of nodes does not exist, restart graph generation
                if(len(possible) == 0):
                    invalid = True
                    break
                
                # Select a random node form list of possible nodes
                target_node = random.choice(possible)

                # Add the edge
                G.add_edge(node, target_node)

            if invalid:
                break
        
        # Return the generated graph if it is connected and no error in generation
        if not invalid and nx.is_connected(G):
            return G

# Number of nodes
# n = 5  # Example value, can be changed as needed

# # Generate the graph
# graph = generate_graph(n)

# import matplotlib.pyplot as plt

# # Draw the graph
# nx.draw(graph, with_labels=True)
# plt.show()
