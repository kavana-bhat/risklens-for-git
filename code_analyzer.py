import ast


def analyze_file(file_path):
    print("\nANALYZING:", file_path)
    print("--------------------")

    with open(file_path, "r", encoding="utf-8") as file:
        code = file.read()

    tree = ast.parse(code)

    print("\nFunctions:")

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            print("-", node.name)

    print("\nClasses:")

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            print("-", node.name)


file_path = input("Enter Python file path: ")

analyze_file(file_path)