# Progress tracker

## Current milestone

Milestone 1 complete: inspected the official ASVS 5.0.0 release, established the
Python package and validated data models, implemented offline import/persistence
and cumulative level selection, and verified the CLI. No later phase is claimed
complete. Project root is `/workspace` (the repository itself is the suggested
`asvs-analyzer/` directory).

## Phases

| Phase | Status | Implemented / remaining |
| --- | --- | --- |
| 1. Dataset integration | Complete for 5.0.0 standard hierarchical JSON | Official fixture, strict schema, full hierarchy/text preservation, version and source hash, cumulative levels, SQLite, CLI |
| 2. Crawler | Not started | Scope authorization, Playwright, redirects/network boundaries, limits, deduplication, browser states, redaction, local fixtures |
| 3. Feature detection | Not started | Authentication, file upload, OAuth/OIDC, WebSocket, GraphQL; structured evidence and limitations |
| 4. Mapping engine | Not started | Review official text; explicit versioned ID mappings separate from detectors |
| 5. Classification/review | Not started | All scoped requirements, evidence-backed decisions, human overrides and audit records |
| 6. Excel reporting | Not started | Summary, requirements, features, crawl results; formatting and safe cell values |
| 7. Tests | Complete for current milestone | 54 passing offline tests; later component and local crawl integration tests remain |
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
- No test crawls a public website. No crawler exists in this milestone.

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
- Only milestone dependencies are required. Crawl/report libraries are optional
  extras. Reserved packages contain no pseudo-implementations.
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
- Crawl safety, credential redaction, feature detection, mappings, applicability,
  review persistence, Excel output, and their tests have not been implemented.
- Package dependencies use bounded ranges, not a full lockfile. Only the documented
  Python/dependency environment has been exercised.

## Next recommended actions

1. Implement the crawler as a separate milestone, starting with validated scope and
   crawl-budget models and sanitized observation/evidence models.
2. Add local application fixtures for rendered links, forms, redirects, authenticated
   browser state, cross-origin requests, WebSocket attempts, and duplicate URLs.
3. Test network scope enforcement, request/page/depth limits, redaction, and blocking
   submissions/state-changing traffic before adding feature detectors.
4. Keep feature mappings and applicability decisions for the subsequent milestones;
   missing evidence must always remain insufficient for automatic N/A.
