import sqlite3

import pytest
from typer.testing import CliRunner

from asvs_analyzer.asvs.importer import import_dataset
from asvs_analyzer.cli import app
from asvs_analyzer.storage.datasets import DatasetStore

runner = CliRunner()


def test_persistence_and_idempotence(official_path, tmp_path):
    imported = import_dataset(official_path)
    path = tmp_path / "nested/db.sqlite3"
    store = DatasetStore(path)
    first = store.save(imported)
    assert store.save(imported) == first
    loaded = DatasetStore(path).load(first)
    assert loaded == imported
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT count(*) FROM datasets").fetchone()[0] == 1


def test_snapshots_not_overwritten(official_path, document, write_document, tmp_path):
    store = DatasetStore(tmp_path / "db.sqlite3")
    first_import = import_dataset(official_path)
    first = store.save(first_import)
    # Different JSON bytes, identical official content: independent source snapshot.
    second_import = import_dataset(write_document(document))
    second = store.save(second_import)
    assert second != first
    assert store.load(first) == first_import
    assert store.load() == second_import
    store.save(first_import)
    assert store.load() == second_import


def test_missing_snapshot(tmp_path):
    store = DatasetStore(tmp_path / "db.sqlite3")
    with pytest.raises(LookupError):
        store.load()
    with pytest.raises(LookupError):
        store.load(100)


def test_cli_import_and_filter(official_path, tmp_path):
    db = str(tmp_path / "db.sqlite3")
    result = runner.invoke(app, ["import-asvs", "--file", str(official_path), "--db", db])
    assert result.exit_code == 0, result.output
    assert "345 requirements" in result.output
    result = runner.invoke(app, ["requirements", "--level", "2", "--db", db, "--dataset-id", "1"])
    assert result.exit_code == 0, result.output
    assert "253 requirements" in result.output
    assert "V1.1.1" in result.output
    assert "V1.2.10" not in result.output  # Level 3


def test_cli_invalid_import_does_not_touch_database(tmp_path):
    db = tmp_path / "db.sqlite3"
    result = runner.invoke(app, ["import-asvs", "--file", str(tmp_path / "missing"), "--db", str(db)])
    assert result.exit_code == 1
    assert "Cannot read dataset" in result.output
    assert not db.exists()


def test_failed_import_preserves_snapshot(official_path, tmp_path):
    db = tmp_path / "db.sqlite3"
    store = DatasetStore(db)
    imported = import_dataset(official_path)
    store.save(imported)
    bad = tmp_path / "bad.json"
    bad.write_text('{}')
    result = runner.invoke(app, ["import-asvs", "--file", str(bad), "--db", str(db)])
    assert result.exit_code == 1
    assert store.load() == imported


@pytest.mark.parametrize("level", ["0", "4", "abc"])
def test_cli_invalid_level(level):
    result = runner.invoke(app, ["requirements", "--level", level])
    assert result.exit_code == 2


def test_cli_missing_database(tmp_path):
    result = runner.invoke(app, ["requirements", "--db", str(tmp_path / "empty.sqlite3")])
    assert result.exit_code == 1
    assert "import-asvs first" in result.output


def test_cli_corrupt_database(tmp_path):
    db = tmp_path / "corrupt.sqlite3"
    db.write_text("not sqlite")
    result = runner.invoke(app, ["requirements", "--db", str(db)])
    assert result.exit_code == 1
    assert "Cannot read dataset database" in result.output


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "import-asvs" in result.output
    assert "requirements" in result.output
