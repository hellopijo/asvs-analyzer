# Architecture

The CLI coordinates small modules; business logic is independent of terminal output.
The current implementation has no network path. Component interfaces will be
introduced when there are actual competing implementations, not speculatively.

| Module | Responsibility | Status |
| --- | --- | --- |
| `config.py` | Database default, supported dataset version, import size bound | Implemented |
| `models/asvs.py` | Validated official hierarchy and scoped requirement records | Implemented |
| `asvs/importer.py` | Bounded UTF-8 JSON parsing, validation, source hash and UTC import time | Implemented |
| `storage/datasets.py` | Transactional SQLite dataset snapshots | Implemented |
| `cli.py` | Typer command parameters and Rich output | Implemented |
| `crawler/` | Playwright observations; HTTPX only when necessary | Reserved package |
| `detectors/` | Authentication, upload, OAuth/OIDC, WebSocket, GraphQL evidence | Reserved package |
| `classifier/` | Deterministic applicability rules and human decision resolution | Reserved package |
| `reporting/` | OpenPyXL output with safe cell serialization | Reserved package |

Current flow:

```text
local JSON -> bounded parser -> strict Pydantic hierarchy -> SQLite snapshot
                                                           |
                                      cumulative level selection -> CLI table
```

The database stores the complete validated hierarchy as JSON, alongside version,
source SHA-256, UTC import timestamp, and numeric snapshot ID. This avoids lossy
flattening and needless SQL tables for immutable reference data. Original JSON
whitespace is not stored; the hash refers to the original input bytes. Future
assessment records must reference a dataset snapshot and selected level.
Parameter binding and a transaction protect writes; identical byte imports are
idempotent. Connections close explicitly. There is no migration system yet: introduce
versioned migrations before extending the persisted schema.

Official aliases are retained during serialization. IDs, descriptions, names,
ordinals, ordering, and level strings are preserved without normalization or
paraphrasing. Level conversion occurs only during selection. Frozen model fields
discourage accidental reassignment, but nested lists are not deeply immutable;
callers must treat validated datasets as read-only.

Future evidence flow:

```text
scope + browser state -> bounded crawler -> redacted observations
  -> feature detectors -> versioned explicit ASVS mappings -> automated decisions
  -> separate human review records -> resolved assessment -> Excel workbook
```

Do not map requirements by keyword similarity. Review actual requirement text,
reference exact official IDs and rule versions, and test each mapping. Always emit
every scoped requirement. Applicable is a relevance judgment, not a pass/fail
verdict. Unmapped or uncertain requirements default to Needs Review. N/A Candidate
needs positive exclusion evidence, never merely missing observations. Confirmed
N/A is human-only and requires reviewer identity, justification, and timestamp.
Human decisions must not overwrite automated decisions.

Before crawler implementation, define scope as explicit origins/path constraints,
including redirects, subresources, WebSockets, popups, and service-worker behavior.
Set separate navigation, page, depth, request, timeout, and rate limits. Block form
submission and state-changing requests; recognize that even GET routes may mutate
state and require conservative navigation exclusions. Never log browser storage
states, request credentials, token-bearing URLs, sensitive cookie values, or response
bodies. Test redaction before writing persistence. Coverage limitations must be
recorded with each run; absence of observed evidence is never proof of absence.

Future observation/evidence models should allow additional sources such as Burp
exports, OpenAPI specifications, and manual evidence without coupling them to
Playwright. No LLM-based classification belongs in this MVP.
