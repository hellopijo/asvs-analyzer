from pathlib import Path
import json

import pytest


@pytest.fixture
def official_path():
    return Path(__file__).resolve().parents[1] / "data/asvs-5.0.0-en.json"


@pytest.fixture
def document(official_path):
    return json.loads(official_path.read_text(encoding="utf-8"))


@pytest.fixture
def write_document(tmp_path):
    def write(document):
        path = tmp_path / "dataset.json"
        path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return path
    return write
