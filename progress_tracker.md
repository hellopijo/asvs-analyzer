# Progress tracker

## Current milestone

Milestone 2 implemented: conservative authorized Playwright crawling, sanitized
observations, SQLite crawl snapshots, CLI options, and real local-browser tests.
Dataset import and cumulative ASVS filtering remain available. Feature detection,
classification, human review, and reporting remain future milestones.

## Phases

| Phase | Status | Implemented / remaining |
| --- | --- | --- |
| 1. Dataset integration | Complete for 5.0.0 standard hierarchical JSON | Official fixture, strict schema, full hierarchy/text preservation, version and source hash, cumulative levels, SQLite, CLI |
| 2. Crawler | Conservative implementation | Explicit authorization, exact origin/path scope, zero-hop redirect inspection, limits, deduplication, state import, sanitized observations, SQLite, CLI and local Chromium fixtures |
| 3. Feature detection | Not started | Authentication, file upload, OAuth/OIDC, WebSocket, GraphQL; structured evidence and limitations |
| 4. Mapping engine | Not started | Review official text; explicit versioned ID mappings separate from detectors |
| 5. Classification/review | Not started | All scoped requirements, evidence-backed decisions, human overrides and audit records |
| 6. Excel reporting | Not started | Summary, requirements, features, crawl results; formatting and safe cell values |
| 7. Tests | Complete for current milestone | 99 passing tests: dataset, scope/redaction, and real Chromium against local HTTP fixtures |
| 8. Documentation | Complete for current milestone | README, architecture, schema/provenance, AGENTS, tracker; expand with each phase |

## Verification performed

- `.venv/bin/python -m pytest -q`: **54 passed** on Python 3.12.14.
- Test dependencies: Pydantic 2.14.0, Typer 0.27.3, Rich 14.3.4, Pytest 9.1.1.
- Installed editable package using `pip install --no-build-isolation --no-deps -e .`
  after installing dependencies; console entry point works.
- Installed CLI imported the bundled release to a temporary SQLite database:
  ASVS 5.0.0, 345 requirements, source SHA-256 retained.
- Installed CLI Level 2 listing succeeded: 253 requirements.
- Tests cover official field-for-field round-trip preservation; UTC import time;
  version, malformed JSON, duplicate keys/IDs, hierarchy, ordinals, missing/extra
  fields, level and size rejection; Unicode/BOM; cumulative counts 70/253/345;
  source hashes, snapshot persistence/idempotence; failed imports preserving data;
  CLI help, parameter validation, missing/corrupt database, and import errors.
- No test crawls a public website. Browser integration fixtures bind loopback only.
- Playwright 1.63.0 and its Chromium build are installed for the crawler tests.
- Browser cache uses `/tmp/asvs-browsers` in this managed workspace.
- Final full suite: **99 passed in 16.61s** using
  `PLAYWRIGHT_BROWSERS_PATH=/tmp/asvs-browsers .venv/bin/python -m pytest -q`.
- The deadline regression caught a queued request escaping during page cleanup;
  pending routes are now explicitly aborted before closing pages. Regression and
  full suite pass after the fix.
- Installed `asvs-analyzer crawl --help` and local CLI crawl/persistence tests pass.

## Technical decisions

- User requested ongoing commits and GitHub pushes after each completed coherent
  change. The workspace's `.git` is a read-only empty placeholder; local history
  uses `.asvs-git` with an explicit work tree. GitHub destination is
  `https://github.com/hellopijo/asvs-analyzer`, branch `main`. Publish through the
  GitHub connector when shell authentication is unavailable, preserving the remote
  history and checking its head before updates.

- Inspected official tag `v5.0.0`, commit
  `61a544f0fdbb7cc1578e0c3a3037a8a2874a944e`.
- Standard hierarchical JSON is supported; flat, legacy, and CycloneDX are rejected.
- Official `Shortcode` and all textual fields remain verbatim. `L` stays a string;
  minimum level is interpreted numerically only when selecting requirements.
- Unknown fields and unsupported versions fail explicitly to prevent silent loss.
- Store validated whole-document snapshots in SQLite with byte SHA-256 and import
  timestamp; normalized assessment/evidence tables can be added in later phases.
- Identical bytes reuse the same ID; distinct bytes create new snapshots. Defaults
  select the newest inserted unique snapshot. Explicit IDs allow stable selection.
- Crawl dependencies remain an optional extra; Chromium is required when crawling.
  Report libraries remain optional for the future reporting milestone.
- Redirects use Playwright fetch with zero redirect hops; scoped document targets
  are queued explicitly. Resource redirects, non-GET/HEAD traffic, workers, frames,
  popups, form submissions and WebSocket handshakes are blocked.
- Page-title text and sensitive header values are intentionally omitted. Path
  redaction remains heuristic; see docs/crawler.md for residual limitations.
- HTTPX is available but unused; no supplemental requests are needed yet.
- Direct shell retrieval was interrupted; the GitHub connector retrieved the pinned
  dataset and upstream license successfully. Fixture tests require no retrieval.

## Known limitations

- Only ASVS 5.0.0 standard hierarchical schema is supported; bundled and tested data
  is English. Other versions/export schemas require explicit adapters and tests.
- Valid subsets are accepted. Import validation does not establish completeness or
  upstream authenticity; a local checksum is provenance, not a digital signature.
- SQLite is for local use, without encryption, schema migrations, or assessment
  records. No authentication secrets are collected by the current implementation.
- Source JSON whitespace is not retained in SQLite; the original bytes are hashed,
  and all modeled fields are preserved. The original fixture remains in `data/`.
- Frozen Pydantic fields do not make nested collections deeply immutable; treat
  datasets as read-only.
- Feature detection, mappings, applicability, review persistence, and Excel output
  have not been implemented. No security verdicts are produced by the crawler.
- Coverage excludes blocked API POSTs, resource redirects, SSO across origins,
  frames/workers/WebSockets, and interaction-only functionality.
- GET endpoints may mutate state; denylisted action names are not comprehensive.
- Raw response bodies are not persisted but Playwright buffers them in memory; no
  response-size budget yet. Arbitrary short secrets in paths cannot be reliably
  recognized. Evidence needs review before sharing. Titles are explicitly omitted.
- Package dependencies use bounded ranges, not a full lockfile. Only the documented
  Python/dependency environment has been exercised.

## Next recommended actions

1. Implement the five structured feature detectors over sanitized observations:
   authentication, upload, OAuth/OIDC, WebSocket, and GraphQL.
2. Preserve observation IDs, confidence and limitations for each detector; blocked
   attempts and missing evidence must not be confused with completed functionality
   or confirmed absence.
3. Review actual ASVS text before introducing explicit, versioned feature mappings.
4. Add classification, human review, and Excel reports in later milestones.
