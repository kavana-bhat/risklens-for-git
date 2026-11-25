import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


@pytest.fixture(scope="session")
def demo_repo(tmp_path_factory):
    dest = tmp_path_factory.mktemp("shop")
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "demo", "make_demo_repo.py"), str(dest)],
        check=True, capture_output=True)
    return str(dest)
