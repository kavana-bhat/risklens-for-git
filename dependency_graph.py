
import ast
import os
import networkx as nx


PROJECT_FOLDER = "sample-project"


def find_imports(file_path):

    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    tree = ast.parse(code)

    imports = []

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):
            for name in node.names:
                imports.append(name.name)

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)

    return imports


# Create graph
graph = nx.DiGraph()


# Find all Python files automatically
files = {}

for file_name in os.listdir(PROJECT_FOLDER):

    if file_name.endswith(".py"):

        path = os.path.join(PROJECT_FOLDER, file_name)

        files[file_name] = path
        graph.add_node(file_name)


# Build dependency relationships
for file_name, path in files.items():

    imports = find_imports(path)

    for imported in imports:

        imported_file = imported.split(".")[-1] + ".py"

        if imported_file in files:

            graph.add_edge(file_name, imported_file)


print("\nDEPENDENCY GRAPH")
print("----------------")

for source, target in graph.edges:

    print(source, "--->", target)