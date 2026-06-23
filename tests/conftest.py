import pytest

from src.config import load_config


@pytest.fixture
def cfg():
    c = load_config()
    c.raw["llm"]["provider"] = "mock"  # never touch a network in tests
    return c
