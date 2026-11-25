
import networkx as nx

# Create dependency graph
graph = nx.DiGraph()

graph.add_edge("app.py", "order.py")
graph.add_edge("order.py", "payment.py")


def find_affected_files(changed_file):

    affected = []

    for file in graph.nodes:

        if nx.has_path(graph, file, changed_file):
            affected.append(file)

    return affected


# Get changed file from Git analyzer
changed_file = input("Enter changed file: ")

# Remove folder path if present
changed_file = changed_file.replace("sample-project/", "")
changed_file = changed_file.replace("\\", "/")

affected = find_affected_files(changed_file)

print("\nIMPACT ANALYSIS")
print("----------------")

print("Changed file:", changed_file)

print("\nPotentially affected files:")

for file in affected:

    if file != changed_file:
        print("-", file)