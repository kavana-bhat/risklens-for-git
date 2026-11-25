import ast


def get_functions(file_path):

    functions = []

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            code = file.read()

        tree = ast.parse(code)

        for node in ast.walk(tree):

            if isinstance(node, ast.FunctionDef):
                functions.append(node.name)

    except Exception:
        pass

    return functions


def analyze_changed_files(repo_path, changed_files):

    results = {}

    for file in changed_files:

        file_name = file.replace("\\", "/")

        # Only analyze Python files
        if not file_name.endswith(".py"):
            continue

        full_path = f"{repo_path}/{file_name}"

        functions = get_functions(full_path)

        results[file_name] = functions

    return results