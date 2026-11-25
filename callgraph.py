"""
callgraph.py  (NEW)

Function-level call graph for Python code, built purely with `ast`.

The original project only had a FILE-level dependency graph
(order.py -> payment.py). This module goes one level deeper:

    payment.py::validate_payment  <-  payment.py::process_payment
                                  <-  order.py::create_order
                                  <-  app.py::run_application

It also knows which functions are tests, so it can answer:
"Is this function reachable from ANY test?"  (static test reachability)

Static analysis is approximate (no dynamic dispatch, no mocks/fixtures),
so results are called "test-reachable", never "covered".
"""

import ast
import posixpath
from collections import defaultdict, deque

import networkx as nx

MODULE_UNIT = "<module>"          # pseudo-function for module-level statements
IGNORED_DIRS = {
    "venv", ".venv", "env", "node_modules", "site-packages",
    "build", "dist", "__pycache__", ".git", ".tox",
}


# ------------------------------------------------------------------
# Path helpers
# ------------------------------------------------------------------

def is_ignored(path):
    parts = path.replace("\\", "/").split("/")
    return any(p in IGNORED_DIRS for p in parts[:-1])


def is_test_file(path):
    p = path.replace("\\", "/")
    base = posixpath.basename(p)
    folders = p.split("/")[:-1]
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or base == "conftest.py"
        or "tests" in folders
        or "test" in folders
    )


def is_test_function(path, qualname):
    return is_test_file(path) and qualname.split(".")[-1].startswith("test")


# ------------------------------------------------------------------
# Parsing a single file
# ------------------------------------------------------------------

class FileInfo:
    """Everything we need to know about one .py file."""

    __slots__ = ("funcs", "classes", "imports", "ok")

    def __init__(self):
        self.funcs = {}      # qualname -> {"args", "calls", "dump"}
        self.classes = set()
        self.imports = {}    # bound name -> (module, name, level)
        self.ok = True       # False when the file has a syntax error


EMPTY = FileInfo()


def _dotted(node):
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _calls_in(nodes):
    found = set()
    for root in nodes:
        for n in ast.walk(root):
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name):
                    found.add(("name", f.id, None))
                elif isinstance(f, ast.Attribute):
                    found.add(("attr", _dotted(f.value), f.attr))
    return sorted(found, key=lambda c: tuple(str(x) for x in c))


def parse_source(source):
    """Parse python source text into a FileInfo (never raises)."""
    info = FileInfo()
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        info.ok = False
        return info

    # imports (anywhere in the file)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    info.imports[a.asname] = (a.name, None, 0)
                else:
                    info.imports[a.name] = (a.name, None, 0)
                    info.imports[a.name.split(".")[0]] = (
                        a.name.split(".")[0], None, 0)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    info.imports[a.asname or a.name] = (
                        n.module, a.name, n.level or 0)

    # functions / methods
    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + child.name
                info.funcs[q] = {
                    "args": [a.arg for a in child.args.args],
                    "calls": _calls_in([child]),
                    "dump": ast.dump(child),
                }
            elif isinstance(child, ast.ClassDef):
                info.classes.add(prefix + child.name)
                visit(child, prefix + child.name + ".")
            else:
                visit(child, prefix)

    visit(tree, "")

    # module-level statements behave like one more "function"
    top = [
        s for s in tree.body
        if not isinstance(
            s, (ast.FunctionDef, ast.AsyncFunctionDef,
                ast.ClassDef, ast.Import, ast.ImportFrom))
    ]
    if top:
        info.funcs[MODULE_UNIT] = {
            "args": [],
            "calls": _calls_in(top),
            "dump": "|".join(ast.dump(s) for s in top),
        }
    return info


# ------------------------------------------------------------------
# The graph
# ------------------------------------------------------------------

class CallGraph:
    """Call graph over a set of files {path: FileInfo}."""

    def __init__(self, files):
        self.files = files
        self.nodes = {}                 # id -> {"path","qual","args"}
        self.g = nx.DiGraph()           # caller -> callee
        self.file_graph = nx.DiGraph()  # importer -> imported
        self.test_nodes = set()
        self._suffix = defaultdict(list)
        self._methods = {}
        self._build()

    # ---- construction -------------------------------------------

    @staticmethod
    def node_id(path, qual):
        return f"{path}::{qual}"

    def _build(self):
        for path in self.files:
            dotted = path[:-3].replace("/", ".")
            if dotted.endswith(".__init__"):
                dotted = dotted[: -len(".__init__")]
            parts = dotted.split(".")
            for i in range(len(parts)):
                self._suffix[".".join(parts[i:])].append(path)
            self.file_graph.add_node(path)

        for path, info in self.files.items():
            by_name = defaultdict(list)
            for q, f in info.funcs.items():
                nid = self.node_id(path, q)
                self.nodes[nid] = {"path": path, "qual": q, "args": f["args"]}
                self.g.add_node(nid)
                if is_test_function(path, q):
                    self.test_nodes.add(nid)
                if "." in q:
                    by_name[q.split(".")[-1]].append(q)
            self._methods[path] = by_name

        for path, info in self.files.items():
            bindings = self._bind(path, info.imports)
            for tgt in bindings.values():
                if tgt[1] != path:
                    self.file_graph.add_edge(path, tgt[1])
            for q, f in info.funcs.items():
                src = self.node_id(path, q)
                for call in f["calls"]:
                    for tpath, tqual in self._targets(
                            path, q, call, bindings):
                        dst = self.node_id(tpath, tqual)
                        if dst != src and dst in self.nodes:
                            self.g.add_edge(src, dst)

    def _module_path(self, importer, module, level):
        if level:
            base = posixpath.dirname(importer)
            for _ in range(level - 1):
                base = posixpath.dirname(base)
            rel = (module or "").replace(".", "/")
            cand = posixpath.join(base, rel) if rel else base
            if not cand:
                return None
            for c in (cand + ".py", posixpath.join(cand, "__init__.py")):
                c = posixpath.normpath(c)
                if c in self.files:
                    return c
            return None
        if not module:
            return None
        cands = self._suffix.get(module, [])
        if not cands:
            return None
        here = posixpath.dirname(importer)
        for c in cands:
            if posixpath.dirname(c) == here:
                return c
        return sorted(cands, key=len)[0]

    def _bind(self, importer, imports):
        """bound name -> ("module", path) | ("symbol", path, name)"""
        out = {}
        for bound, (module, name, level) in imports.items():
            if name is None:
                p = self._module_path(importer, module, 0)
                if p:
                    out[bound] = ("module", p)
                continue
            sub = f"{module}.{name}" if module else name
            p_sub = self._module_path(importer, sub, level)
            if p_sub:
                out[bound] = ("module", p_sub)
                continue
            p = self._module_path(importer, module, level)
            if p:
                out[bound] = ("symbol", p, name)
        return out

    def _targets(self, path, qual, call, bindings):
        kind, a, b = call
        info = self.files[path]
        out = []

        if kind == "name":
            if a in info.funcs:
                out.append((path, a))
            elif a in info.classes and f"{a}.__init__" in info.funcs:
                out.append((path, f"{a}.__init__"))
            elif a in bindings and bindings[a][0] == "symbol":
                p, n = bindings[a][1], bindings[a][2]
                ti = self.files[p]
                if n in ti.funcs:
                    out.append((p, n))
                elif f"{n}.__init__" in ti.funcs:
                    out.append((p, f"{n}.__init__"))
            return out

        # attribute call:  base.meth(...)
        base, meth = a, b
        tgt = bindings.get(base) if base else None
        if base in ("self", "cls"):
            cls = qual.rsplit(".", 1)[0] if "." in qual else None
            if cls and f"{cls}.{meth}" in info.funcs:
                out.append((path, f"{cls}.{meth}"))
            else:
                out += [(path, q) for q in self._methods[path].get(meth, [])]
        elif tgt and tgt[0] == "module":
            ti = self.files[tgt[1]]
            if meth in ti.funcs:
                out.append((tgt[1], meth))
            elif f"{meth}.__init__" in ti.funcs:
                out.append((tgt[1], f"{meth}.__init__"))
        elif tgt and tgt[0] == "symbol":
            p, n = tgt[1], tgt[2]
            if f"{n}.{meth}" in self.files[p].funcs:
                out.append((p, f"{n}.{meth}"))
        elif base and base in info.classes and f"{base}.{meth}" in info.funcs:
            out.append((path, f"{base}.{meth}"))
        else:
            # unknown receiver: look for a method of that name in this file
            # and in the project files this file imports directly
            scope = {path} | {t[1] for t in bindings.values()}
            for p in scope:
                out += [(p, q) for q in self._methods[p].get(meth, [])]
        return out

    # ---- queries -------------------------------------------------

    def _reach(self, starts, reverse):
        seen = set(starts)
        queue = deque(starts)
        step = self.g.predecessors if reverse else self.g.successors
        while queue:
            n = queue.popleft()
            for m in step(n):
                if m not in seen:
                    seen.add(m)
                    queue.append(m)
        return seen

    def callers(self, ids):
        """Transitive callers of `ids` (including ids themselves)."""
        return self._reach([i for i in ids if i in self.g], reverse=True)

    def test_reachable(self):
        """All functions reachable from at least one test function."""
        return self._reach(list(self.test_nodes), reverse=False)

    def tests_reaching(self, ids):
        """Test functions that (transitively) call any of `ids`."""
        return self.callers(ids) & self.test_nodes

    def dependents_of_file(self, path):
        """Files that import `path`, directly or transitively."""
        if path not in self.file_graph:
            return set()
        return nx.ancestors(self.file_graph, path)

    def import_name(self, path):
        """The module name a test would use to import `path`."""
        parts = path[:-3].split("/")
        name = [parts[-1]]
        d = parts[:-1]
        while d and posixpath.join(*d, "__init__.py") in self.files:
            name.insert(0, d[-1])
            d = d[:-1]
        return ".".join(name)


# ------------------------------------------------------------------
# Convenience loaders
# ------------------------------------------------------------------

def files_from_directory(root):
    """Parse every .py file below `root` -> {relative_path: FileInfo}."""
    import os
    infos = {}
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for n in names:
            if n.endswith(".py"):
                full = os.path.join(folder, n)
                rel = os.path.relpath(full, root).replace(os.sep, "/")
                try:
                    with open(full, "r", encoding="utf-8",
                              errors="ignore") as fh:
                        infos[rel] = parse_source(fh.read())
                except OSError:
                    pass
    return infos
