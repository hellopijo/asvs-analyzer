# Instructions for contributors and AI coding agents

## User-authorized Git workflow

Commit each completed coherent change after appropriate checks, and push it to the
configured GitHub branch. The user requested this ongoing workflow; no repeated
confirmation is needed for routine commits and pushes. Do not force-push or include
credentials, browser state, generated databases, reports, or virtual environments.
If the destination or access is missing, preserve a local commit and report the
blocker accurately. This workspace has a read-only placeholder `.git`; local Git
metadata lives in `.asvs-git`. Use
`git --git-dir=/workspace/.asvs-git --work-tree=/workspace` here. On a normal clone,
use ordinary Git commands.

The configured destination is `https://github.com/hellopijo/asvs-analyzer`, branch
`main`. Use the GitHub connector for publishing if shell GitHub authentication is
unavailable. Preserve remote history and check the current branch head before
updating it; never overwrite concurrent changes.

## Scope and architecture

Read README.md and progress_tracker.md first. This repository currently implements
the dataset foundation and a conservative browser crawler. Do not imply that
reserved packages implement detection, classification, review, or reporting. Follow the user's current milestone
scope. Keep CLI presentation, domain models, import, crawling, detectors, mappings,
classification, persistence, and reporting separate. Prefer small functions over
frameworks or speculative abstraction.

## Conventions

Use Python 3.12+, type annotations on public APIs, Pydantic v2 models, pathlib paths,
UTC timestamps, parameterized SQLite queries, and explicit connection lifetimes.
Preserve official ASVS IDs and descriptions exactly. Do not edit the bundled official
dataset to fix a failing test. Inspect upstream schema changes and add deliberate,
versioned adapters. Keep original automated decisions separate from human decisions.
Do not add LLM classification or additional application frameworks.

## Testing

Run `python -m pytest -q` using the project's virtual environment, with the crawl
extra and Chromium installed for full browser integration coverage. Add meaningful
tests for changed behavior and rejection paths. Dataset tests must remain offline;
crawl tests must use authorized local fixtures/mocks, never public sites. Test scope
boundaries, redirects, request limits, redaction, and human-only Confirmed N/A rules
when those modules are implemented. Update progress_tracker.md with actual results
and outstanding limitations; never report unrun tests as passing.

## Security boundaries

The tool assists applicability scoping, not vulnerability scanning or compliance
certification. Never equate not detected with not applicable. Never assign Confirmed
N/A automatically. Never omit requirements without mappings. Human exclusion needs
reviewer identity, justification, and timestamp. Future crawls require explicit
authorization and scope enforced on all relevant network paths, not just navigation.
No form submission, authentication brute force, access-control bypass, destructive
actions, or active exploitation. Redact credentials, tokens, sensitive cookies and
URLs before storage/output; do not store sensitive response bodies. Treat browser
storage-state files as secrets. Never commit them. Make spreadsheet exports safe
against formula injection while preserving official source text in storage.
