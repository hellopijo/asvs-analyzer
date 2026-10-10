"""Append-only sanitized crawl snapshots; independent of dataset storage."""
from pathlib import Path
import sqlite3
from asvs_analyzer.models.crawl import CrawlRun


class CrawlStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def save(self, run: CrawlRun) -> str:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        try:
            with connection:
                connection.execute('CREATE TABLE IF NOT EXISTS crawl_runs (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, document TEXT NOT NULL)')
                connection.execute('INSERT INTO crawl_runs VALUES (?, ?, ?)', (run.id, run.started_at.isoformat(), run.model_dump_json()))
        finally:
            connection.close()
        return run.id

    def load(self, run_id: str) -> CrawlRun:
        connection = sqlite3.connect(self.path)
        try:
            row = connection.execute('SELECT document FROM crawl_runs WHERE id = ?', (run_id,)).fetchone()
        finally:
            connection.close()
        if row is None:
            raise LookupError('Crawl run not found')
        return CrawlRun.model_validate_json(row[0])
