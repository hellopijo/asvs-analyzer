"""Transactional, content-addressed dataset snapshots in local SQLite."""
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import sqlite3

from asvs_analyzer.asvs.importer import ImportedDataset
from asvs_analyzer.models.asvs import Dataset


class DatasetStore:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS datasets (
                    id INTEGER PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    document TEXT NOT NULL
                )""")
                yield connection
        finally:
            connection.close()

    def save(self, imported: ImportedDataset) -> int:
        with self.connection() as connection:
            connection.execute(
                "INSERT INTO datasets (sha256, version, imported_at, document) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(sha256) DO NOTHING",
                (imported.sha256, imported.dataset.version, imported.imported_at.isoformat(),
                 imported.dataset.model_dump_json(by_alias=True)),
            )
            return connection.execute(
                "SELECT id FROM datasets WHERE sha256 = ?", (imported.sha256,)
            ).fetchone()[0]

    def load(self, dataset_id: int | None = None) -> ImportedDataset:
        with self.connection() as connection:
            if dataset_id is None:
                row = connection.execute(
                    "SELECT sha256, imported_at, document FROM datasets ORDER BY id DESC LIMIT 1"
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT sha256, imported_at, document FROM datasets WHERE id = ?", (dataset_id,)
                ).fetchone()
        if row is None:
            raise LookupError("Dataset not found; run import-asvs first or check --dataset-id")
        return ImportedDataset(Dataset.model_validate_json(row[2]), row[0], datetime.fromisoformat(row[1]))
