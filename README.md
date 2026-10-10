# ASVS Applicability Analyzer

A Python CLI foundation for evidence-driven OWASP ASVS applicability assessment.
This is a reconnaissance and scoping assistant, not a vulnerability scanner.
Applicability does not imply vulnerability, and crawling cannot establish ASVS compliance.

**Current milestone:** official ASVS 5.0.0 dataset import and cumulative level
selection, plus conservative Playwright crawling with sanitized SQLite evidence.
Feature detection, mapping, classification, human review, and Excel reporting remain
planned, not implemented.

## Install

Python 3.12 or newer is required. From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,crawl]'
python -m playwright install chromium
```

Pydantic, Typer, and Rich support the core CLI; SQLite is in the standard library.
The `crawl` extra installs Playwright and HTTPX (reserved for supplemental inspection).
OpenPyXL remains the optional `report` extra. On Linux, browser system libraries may
need installation with `python -m playwright install --with-deps chromium`.
For a dataset-only installation omit the `crawl` extra and browser installation.

## Use

An official release fixture is included, with its provenance and license in `data/`.
Dataset commands operate offline. The crawl command contacts the explicitly
authorized target and persists sanitized observations locally.

```bash
asvs-analyzer import-asvs --file data/asvs-5.0.0-en.json
asvs-analyzer requirements --level 2
asvs-analyzer requirements --level 1 --dataset-id 1
asvs-analyzer --help
asvs-analyzer import-asvs --help
```

Use `--db /path/to/assessment.sqlite3` on either command to override the default
`data/asvs.sqlite3` (relative to your working directory). Parent directories are
created as needed. There are no environment variables or configuration files yet.
The importer prints a dataset ID and SHA-256 of the original file bytes.
Use the printed ID to select a specific snapshot; the default is the most recently
inserted unique snapshot. Reimporting identical bytes retains the original ID and
import timestamp. Different file bytes produce a separate snapshot, even if the
version and parsed content are identical. Nothing is silently replaced.

| Selected level | Included minimum levels | Official 5.0.0 count |
| --- | --- | --- |
| 1 | 1 | 70 |
| 2 | 1, 2 | 253 |
| 3 | 1, 2, 3 | 345 |

The `requirements` command lists official IDs, minimum levels, chapter and section
names, and full descriptions. It does **not** assign applicability classifications.
Descriptions may contain additional level-specific expectations; those remain
verbatim. `analyze`, `review`, and `report` are not available yet.

## Dataset contract

Supported input is the official English **hierarchical standard JSON** from ASVS
release `v5.0.0`, named
`OWASP_Application_Security_Verification_Standard_5.0.0_en.json` in
[OWASP/ASVS](https://github.com/OWASP/ASVS/tree/v5.0.0/5.0/docs_en).
The schema and provenance are documented in [docs/dataset.md](docs/dataset.md).
Flat, legacy, and CycloneDX exports, other versions, and unknown fields are rejected.

Validation rejects duplicate JSON keys or identifiers, missing or blank text,
invalid minimum levels, mismatched hierarchy and ordinals, malformed UTF-8 JSON,
and files larger than 10 MiB. Errors do not echo invalid input values. Imports are
validated before any database access. A syntactically valid subset is accepted;
schema validation and a checksum **do not authenticate a local file as official**
or guarantee it is complete. Use the pinned bundled release for the full standard.

## Test

```bash
python -m pytest -q
```

Tests use the bundled official JSON fixture and temporary files/databases. They
never crawl public websites or require network access. Coverage includes full
round-trip preservation, version/schema rejection, cumulative filtering, database
snapshots, and CLI success/error paths. With the `crawl` extra installed, the suite
also launches Chromium against ephemeral loopback HTTP servers and checks actual
received traffic. Browser integration tests are skipped only when Playwright is not
installed; when installed, missing Chromium is a test failure. Sandboxed execution
needs permission to bind loopback sockets and launch Chromium.

## Architecture and boundaries

See [docs/architecture.md](docs/architecture.md) for component responsibilities,
[AGENTS.md](AGENTS.md) for contributor rules, and
[progress_tracker.md](progress_tracker.md) for status and next actions.

Crawling requires `--authorized` and restricts requests to the target's exact origin
and optional path subtree. Redirects are intercepted before following, and scoped
navigation destinations are queued. Non-GET/HEAD requests, form submissions,
WebSocket handshakes, frames, workers, and popups are blocked. See
[docs/crawler.md](docs/crawler.md) for the safety model and coverage limitations.

```bash
asvs-analyzer crawl --target http://localhost:3000 --authorized \
  --scope-path / --max-depth 3 --max-pages 50 --max-requests 500 \
  --timeout-ms 10000 --duration-seconds 120 --delay-ms 200 \
  --exclude-path /admin --db data/asvs.sqlite3
```

Use `--storage-state .auth/state.json` for manually supplied Playwright authentication
state. Keep this file secret; the crawler never exports it. `--exclude-path` can be
repeated. `--settle-ms` sets the finite wait for rendered DOM content (default 300).
The CLI prints the persisted run ID, page/request counts, and stop reason.
No detected-feature or applicability classifications are produced yet.

Missing feature evidence must never imply N/A. All scoped requirements must appear
in future assessments; insufficient evidence defaults to Needs Review. Confirmed
N/A will require an identified human reviewer, justification, and timestamp stored
separately from the automated decision.

The next milestone is structured feature detection over these sanitized observations.
The crawler intentionally omits page titles and sensitive header values to reduce
data exposure; those omissions must remain visible in eventual reports.
