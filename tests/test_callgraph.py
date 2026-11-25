from callgraph import CallGraph, parse_source

SRC = {
    "pkg/__init__.py": "",
    "pkg/payment.py": (
        "def validate(a):\n    return a > 0\n"
        "def pay(a):\n    return validate(a)\n"
        "def refund(a):\n    return a\n"
        "class Gate:\n"
        "    def run(self, a):\n        return self.check(a)\n"
        "    def check(self, a):\n        return pay(a)\n"),
    "pkg/order.py": (
        "from .payment import pay\nfrom . import payment\n"
        "def create(a):\n    payment.refund(a)\n    return pay(a)\n"
        "def cancel(i):\n    return i\n"),
    "app.py": "from pkg.order import create\ndef run():\n    return create(1)\n",
    "tests/test_order.py": (
        "from pkg.order import create\n"
        "def test_create():\n    assert create(1)\n"),
}


def graph():
    return CallGraph({p: parse_source(s) for p, s in SRC.items()})


def edges(g):
    return set(g.g.edges)


def test_resolves_symbol_module_and_method_calls():
    e = edges(graph())
    assert ("app.py::run", "pkg/order.py::create") in e
    assert ("pkg/order.py::create", "pkg/payment.py::pay") in e          # from .x import f
    assert ("pkg/order.py::create", "pkg/payment.py::refund") in e       # module.f()
    assert ("pkg/payment.py::pay", "pkg/payment.py::validate") in e
    assert ("pkg/payment.py::Gate.run", "pkg/payment.py::Gate.check") in e  # self.m()


def test_test_reachability():
    g = graph()
    reach = g.test_reachable()
    assert "pkg/payment.py::validate" in reach          # test -> create -> pay -> validate
    assert "pkg/order.py::cancel" not in reach
    assert "pkg/payment.py::Gate.run" not in reach


def test_callers_and_tests_reaching():
    g = graph()
    callers = g.callers(["pkg/payment.py::validate"])
    assert {"pkg/payment.py::pay", "pkg/order.py::create", "app.py::run"} <= callers
    assert g.tests_reaching(["pkg/payment.py::validate"]) == {"tests/test_order.py::test_create"}


def test_file_dependents_and_import_name():
    g = graph()
    assert {"pkg/order.py", "app.py"} <= g.dependents_of_file("pkg/payment.py")
    assert g.import_name("pkg/payment.py") == "pkg.payment"
    assert g.import_name("app.py") == "app"


def test_syntax_error_files_are_skipped_not_fatal():
    info = parse_source("def broken(:\n    pass")
    assert info.ok is False and info.funcs == {}
    g = CallGraph({"a.py": info, "b.py": parse_source("def f():\n    pass")})
    assert "b.py::f" in g.nodes
