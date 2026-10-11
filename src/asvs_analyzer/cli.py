"""Dataset and authorized reconnaissance commands."""
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

app = typer.Typer(no_args_is_help=True, help="ASVS applicability scoping assistant. No security verdicts.")
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


@app.command("crawl")
def crawl_command(
    target: Annotated[str, typer.Option(help="Authorized HTTP(S) target; defines the only allowed origin.")],
    authorized: Annotated[bool, typer.Option("--authorized", help="Confirm you are authorized to crawl this target.")] = False,
    scope_path: Annotated[str, typer.Option(help="Allowed path subtree for ALL requests.")] = "/",
    max_depth: Annotated[int, typer.Option(min=0, max=20)] = 3,
    max_pages: Annotated[int, typer.Option(min=1, max=10000)] = 50,
    max_requests: Annotated[int, typer.Option(min=1, max=100000)] = 500,
    timeout_ms: Annotated[int, typer.Option(min=100, max=120000)] = 10000,
    duration_seconds: Annotated[int, typer.Option(min=1, max=86400)] = 120,
    delay_ms: Annotated[int, typer.Option(min=0, max=60000)] = 200,
    settle_ms: Annotated[int, typer.Option(min=0, max=10000)] = 300,
    storage_state: Annotated[Path | None, typer.Option(help="Secret Playwright browser state file; never stored in the report.")] = None,
    exclude_path: Annotated[list[str] | None, typer.Option(help="Additional excluded path subtree; repeatable.")] = None,
    db: DatabaseOption = Settings().database,
) -> None:
    """Observe an authorized application without submitting forms or assessing vulnerabilities."""
    import asyncio
    from asvs_analyzer.models.crawl import CrawlConfig
    from asvs_analyzer.storage.crawls import CrawlStore
    try:
        config = CrawlConfig(target=target, authorized=authorized, scope_path=scope_path,
            max_depth=max_depth, max_pages=max_pages, max_requests=max_requests,
            timeout_ms=timeout_ms, duration_seconds=duration_seconds, delay_ms=delay_ms,
            settle_ms=settle_ms, storage_state=storage_state, exclude_paths=exclude_path or [])
    except ValidationError:
        fail("Invalid crawl configuration; use --authorized, an HTTP(S) URL without credentials, and a scope path containing the target")
    try:
        from asvs_analyzer.crawler.browser import CrawlError, crawl
    except ImportError:
        fail("Install crawl dependencies: pip install -e '.[crawl]' and python -m playwright install chromium")
    try:
        run = asyncio.run(crawl(config))
        run_id = CrawlStore(db).save(run)
    except CrawlError as exc:
        fail(str(exc))
    except (OSError, sqlite3.Error):
        fail("Cannot persist crawl; check database path, permissions, and format")
    console.print(f"Crawl {run_id}: {len(run.pages)} pages, {run.requests_sent} requests; stop: {run.stop_reason}.")
    console.print("Observations stored with redacted URLs and cookie attributes. No applicability or security verdicts.")


@app.command("detect")
def detect_command(
    run_id: Annotated[str, typer.Option(help="Crawl ID printed by the crawl command.")],
    db: DatabaseOption = Settings().database,
    details: Annotated[bool, typer.Option(help="Show supporting evidence references and limitations.")] = False,
) -> None:
    """Identify feature hints from a saved crawl, without contacting the target."""
    from asvs_analyzer.detectors.engine import detect_features
    from asvs_analyzer.storage.crawls import CrawlStore
    from asvs_analyzer.storage.features import FeatureStore
    if not db.is_file():
        fail("Database not found; run crawl first or supply --db")
    try:
        result = detect_features(CrawlStore(db).load(run_id))
        FeatureStore(db).save(result)
    except LookupError:
        fail("Crawl ID not found; use the ID printed by crawl")
    except (OSError, sqlite3.Error, ValidationError, ValueError):
        fail("Cannot read crawl or save feature results; check database integrity and permissions")
    console.print(f"Feature run {result.id} | detector version {result.detector_version}")
    table = Table("Feature", "Status", "Confidence", "Evidence count")
    for feature in result.features:
        table.add_row(feature.feature, feature.status, f"{feature.confidence:.0%}", str(len(feature.evidence)))
    console.print(table)
    console.print("Not observed means no supporting evidence was found; the feature may still exist.")
    if details:
        for feature in result.features:
            console.print(feature.feature)
            for evidence in feature.evidence:
                console.print(f"  {evidence.reference}: {evidence.summary} ({evidence.source_url})")
            for limitation in feature.limitations:
                console.print(f"  Limitation: {limitation}")
        for limitation in result.limitations:
            console.print(f"Coverage: {limitation}")


if __name__ == "__main__":
    app()
