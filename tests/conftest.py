import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qe.config import load_instruments, load_research  # noqa: E402
from qe.synthetic import generate  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return load_research()


@pytest.fixture(scope="session")
def instruments():
    return load_instruments()


@pytest.fixture(scope="session")
def small_bars():
    return generate(start="2021-03-01", end="2021-03-20", seed=11)
