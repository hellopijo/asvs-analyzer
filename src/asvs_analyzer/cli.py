"""Dataset commands. Assessment commands arrive in later milestones."""
from pathlib import Path
import sqlite3
from typing import Annotated

from pydantic import ValidationError
from rich.console import Console
from rich.table import Table
import typer

from asvs_analyzer.asvs.importer import DatasetImportError, import_dataset
from asvs_analyzer.config import Settings
from asvs_analyzer.storage.datasets import DatasetStore

app = typer.Typer(no_args_is_help=True, help="ASVS applicability scoping assistant. Dataset milestone; no security verdicts.")
console = Console(markup=False)
errors = Console(stderr=True, markup=False)
DatabaseOption = Annotated[Path, typer.Option("--db", help="Local SQLite database path.")]


def fail(message: str):
    errors.print(f"Error: {message}")
    raise typer.Exit(1)


@app.command("import-asvs")
def import_asvs(
    file: Annotated[Path, typer.Option("--file", help="Official hierarchical ASVS 5.0.0 JSON file.")],
    db: DatabaseOption = Settings().database,
):
    """Validate and persist every requirement, preserving its official text."""
    try:
        imported = import_dataset(file)
        dataset_id = DatasetStore(db).save(imported)
    except DatasetImportError as exc:
        fail(str(exc))
    except (OSError, sqlite3.Error):
        fail("Cannot write SQLite database; check its path, permissions, and format")
    console.print(f"Imported ASVS {imported.dataset.version}: {len(imported.dataset.select_level(3))} requirements; dataset ID {dataset_id}.")
    console.print(f"Source SHA-256: {imported.sha256}")


@app.command("requirements")
def requirements(
    level: Annotated[int, typer.Option(min=1, max=3, help="Cumulative verification level.")] = 2,
    db: DatabaseOption = Settings().database,
    dataset_id: Annotated[int | None, typer.Option(min=1, help="Snapshot ID; defaults to newest unique import.")] = None,
):
    """List requirements in the selected level without classifying applicability."""
    try:
        imported = DatasetStore(db).load(dataset_id)
    except LookupError as exc:
        fail(str(exc))
    except (OSError, sqlite3.Error, ValidationError, ValueError):
        fail("Cannot read dataset database; check its path and integrity")
    selected = imported.dataset.select_level(level)
    console.print(f"ASVS {imported.dataset.version} | Level {level} (cumulative) | {len(selected)} requirements")
    table = Table("ID", "Level", "Chapter", "Section", "Description")
    for item in selected:
        table.add_row(item.requirement.id, item.requirement.level, item.chapter_name, item.section_name, item.requirement.description)
    console.print(table)


if __name__ == "__main__":
    app()
