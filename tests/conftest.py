from pathlib import Path
import pytest
from scripts.corpus import generate


@pytest.fixture(scope="session")
def corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("corpus")
    generate(root)
    return root
