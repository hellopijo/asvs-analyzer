"""Append-only detector results referencing their exact source crawl snapshot."""
from pathlib import Path
import sqlite3
from asvs_analyzer.models.features import DetectionRun


class FeatureStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, run: DetectionRun) -> str:
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS feature_runs (id TEXT PRIMARY KEY, crawl_id TEXT NOT NULL, document TEXT NOT NULL)')
                connection.execute('INSERT INTO feature_runs VALUES (?, ?, ?)', (run.id, run.crawl_id, run.model_dump_json()))
        finally:
            connection.close()
        return run.id

    def load(self, run_id: str) -> DetectionRun:
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute('SELECT document FROM feature_runs WHERE id = ?', (run_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise LookupError('Feature run not found')
        return DetectionRun.model_validate_json(row[0])
