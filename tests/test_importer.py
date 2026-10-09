import hashlib
import json

import pytest

from asvs_analyzer.asvs.importer import DatasetImportError, import_dataset
from asvs_analyzer.config import MAX_DATASET_BYTES


def test_official_release_roundtrip_and_provenance(official_path, document):
    imported = import_dataset(official_path)
    assert imported.dataset.version == "5.0.0"
    assert len(imported.dataset.chapters) == 17
    assert imported.dataset.model_dump(by_alias=True) == document
    assert imported.sha256 == hashlib.sha256(official_path.read_bytes()).hexdigest()
    assert imported.imported_at.utcoffset().total_seconds() == 0
    assert len(imported.dataset.select_level(3)) == 345


@pytest.mark.parametrize("level,count", [(1, 70), (2, 253), (3, 345)])
def test_cumulative_levels(official_path, level, count):
    dataset = import_dataset(official_path).dataset
    selected = dataset.select_level(level)
    assert len(selected) == count
    assert all(int(row.requirement.level) <= level for row in selected)
    assert {row.requirement.id for row in dataset.select_level(1)} <= {row.requirement.id for row in selected}
    assert all(row.chapter_name and row.section_name for row in selected)


@pytest.mark.parametrize("level", [0, 4, -1, True, False, 2.0, "2", None])
def test_invalid_level(official_path, level):
    with pytest.raises(ValueError, match="Verification level"):
        import_dataset(official_path).dataset.select_level(level)


@pytest.mark.parametrize("version", ["4.0.3", "5.0", "5.0.1", "5.0.0-rc1", None])
def test_reject_unsupported_version(document, write_document, version):
    document["Version"] = version
    with pytest.raises(DatasetImportError, match="Version"):
        import_dataset(write_document(document))


@pytest.mark.parametrize("field,value", [("L", "4"), ("L", 2), ("L", True), ("Description", " "), ("Description", None), ("Shortcode", "1.1.1"), ("Ordinal", True), ("Ordinal", 99)])
def test_invalid_requirement(document, write_document, field, value):
    document["Requirements"][0]["Items"][0]["Items"][0][field] = value
    with pytest.raises(DatasetImportError):
        import_dataset(write_document(document))


@pytest.mark.parametrize("node", ["chapter", "section", "requirement"])
def test_reject_duplicate_identifiers(document, write_document, node):
    items = document["Requirements"]
    if node in ("section", "requirement"):
        items = items[0]["Items"]
    if node == "requirement":
        items = items[0]["Items"]
    items.append(items[0])
    with pytest.raises(DatasetImportError):
        import_dataset(write_document(document))


@pytest.mark.parametrize("node", ["section", "requirement"])
def test_reject_wrong_parent(document, write_document, node):
    section = document["Requirements"][0]["Items"][0]
    if node == "section":
        section["Shortcode"] = "V2.1"
    else:
        section["Items"][0]["Shortcode"] = "V1.2.1"
    with pytest.raises(DatasetImportError):
        import_dataset(write_document(document))


@pytest.mark.parametrize("case", ["missing", "extra", "empty", "flat"])
def test_reject_schema_changes(document, write_document, case):
    if case == "missing":
        del document["Requirements"][0]["Items"][0]["Items"][0]["L"]
    elif case == "extra":
        document["Unknown"] = "unexpected"
    elif case == "empty":
        document["Requirements"] = []
    else:
        document = document["Requirements"][0]["Items"][0]["Items"]
    with pytest.raises(DatasetImportError):
        import_dataset(write_document(document))


@pytest.mark.parametrize("raw", [b"{", b"\xff", b'{"Version":"5.0.0","Version":"4.0.3"}', b"[" * 2000])
def test_invalid_json(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    with pytest.raises(DatasetImportError):
        import_dataset(path)


def test_missing_file(tmp_path):
    with pytest.raises(DatasetImportError, match="Cannot read"):
        import_dataset(tmp_path / "missing.json")


def test_size_limit(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b" " * (MAX_DATASET_BYTES + 1))
    with pytest.raises(DatasetImportError, match="10 MiB"):
        import_dataset(path)


def test_error_does_not_echo_input(document, write_document):
    document["Version"] = "SECRET_SENTINEL"
    with pytest.raises(DatasetImportError) as error:
        import_dataset(write_document(document))
    assert "SECRET_SENTINEL" not in str(error.value)


def test_bom_and_unicode_preserved(document, tmp_path):
    path = tmp_path / "bom.json"
    path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8-sig")
    assert import_dataset(path).dataset.model_dump(by_alias=True) == document
