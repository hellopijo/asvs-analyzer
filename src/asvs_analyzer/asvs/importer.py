"""Offline, bounded import; no schema guessing or silent record dropping."""
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

from pydantic import ValidationError

from asvs_analyzer.config import MAX_DATASET_BYTES
from asvs_analyzer.models.asvs import Dataset


class DatasetImportError(ValueError):
    """Invalid, unsupported, or unreadable dataset."""


@dataclass(frozen=True)
class ImportedDataset:
    dataset: Dataset
    sha256: str
    imported_at: datetime


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DatasetImportError("Duplicate JSON object key")
        result[key] = value
    return result


def import_dataset(path: Path) -> ImportedDataset:
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_DATASET_BYTES + 1)
    except OSError as exc:
        raise DatasetImportError("Cannot read dataset file; check the path and permissions") from exc
    if len(raw) > MAX_DATASET_BYTES:
        raise DatasetImportError("Dataset exceeds the 10 MiB import limit")
    try:
        document = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_keys)
        dataset = Dataset.model_validate(document)
    except ValidationError as exc:
        # Deliberately omit input values from diagnostics.
        first = exc.errors(include_input=False, include_url=False)[0]
        location = ".".join(str(part) for part in first["loc"]) or "root"
        raise DatasetImportError(
            f"Invalid ASVS 5.0.0 hierarchical schema at {location} ({first['type']}); "
            "use the standard .json file, not flat, legacy, or CycloneDX JSON"
        ) from exc
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise DatasetImportError("Dataset must contain valid UTF-8 JSON") from exc
    return ImportedDataset(dataset, sha256(raw).hexdigest(), datetime.now(UTC))
