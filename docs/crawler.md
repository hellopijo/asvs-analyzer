# Crawler milestone

## Scope and execution

`--target` defines the only allowed origin, including scheme and effective port.
`--scope-path` applies a path-segment boundary to all requests, including resources.
Canonicalization removes fragments, normalizes host/default ports, and rejects
credentials, ambiguous encoded separators, double encodings, dot segments, controls,
and backslashes. Distinct query values remain distinct internally for discovery;
redacted evidence may therefore show identical URLs for different raw query values.
Observation UUIDs distinguish evidence records.

Breadth-first navigation is sequential. The start page has depth zero; links and
redirect destinations increase depth by one. Redirect loops and fragment aliases
are deduplicated. Queue size is capped at 20 times the page budget. Playwright runs
JavaScript with a finite configurable settling time and then collects link targets,
form methods/actions/encodings, and input types. It does not click controls.

Every HTTP request is intercepted at browser-context level. Only GET/HEAD requests
that pass scope, exclusions, and navigation checks are fetched. Requests are paced
serially. Fetch uses `max_redirects=0` and `max_retries=0`: 3xx responses are recorded,
never delivered as redirects to the browser. Valid main-document destinations are
queued; resource redirects are blocked. This avoids relying on browser route hooks
being invoked for every redirect hop. Refresh and Link response headers are removed.
An intercepted redirect can produce a page navigation error alongside its recorded
3xx status; this is expected and is not a vulnerability finding.

Subframes, popups, downloads, service workers, Web Workers, WebRTC constructors,
form submission and non-GET/HEAD traffic are disabled or blocked. WebSocket attempts
are recorded and closed without connecting to the server. Cookie attributes and
selected response header presence/authentication schemes are collected. TLS
verification remains enabled. Raw error messages from browser operations are not
stored or printed.

## Budgets and persistence

CLI options include maximum page count, link depth, outgoing HTTP requests,
per-request/navigation timeout, inter-request delay, rendering settle time, and
whole crawl duration. The duration timer covers browsing, not browser installation,
startup, or cleanup. Requests already dispatched may finish during cleanup. Cookies,
DOM extraction and observation counts are capped. Response bodies are not persisted,
but Playwright buffers fetched responses in memory; there is no response-size budget
yet. Explicit stop reasons cover page, request, and duration limits. All runs retain
the selected numeric limits and coverage limitations.

`crawl_runs` is an additive SQLite table, independent of the reference dataset table.
It stores a run UUID, UTC start time, and validated JSON with pages, observations,
finish time, stop reason, limits, and limitations. Runs are append-only; duplicate
run IDs are rejected. The Python `CrawlStore.load(run_id)` API retrieves a snapshot.
There is no browse/export CLI for run evidence yet and no formal migration framework.

## Privacy and authenticated state

The crawler stores no request/response bodies, input values, page-title text, cookie
values, browser storage values, or query values. It retains selected header presence
and constrained content types/authentication schemes. Unknown query parameter names
are replaced with `parameter`; recognized OAuth and GraphQL parameter names remain.
URL userinfo and fragments are discarded. Long token-like path segments and known
cookie/local-storage secrets are masked. Original URLs exist only in process memory.
Path redaction is heuristic: arbitrary short secrets or personal data embedded in
route names cannot be reliably recognized. Evidence still needs human review before
sharing. Titles are explicitly marked omitted rather than represented as captured.

`--storage-state` accepts a manually created Playwright JSON state (maximum 5 MiB).
Only exact-origin local storage and matching-host cookies are imported. Cross-host
SSO state is not imported. The path and contents are never saved in the crawl run.
Keep state under the ignored `.auth/` directory. Capture must already be authorized;
the tool never attempts login, credential guessing, or access-control bypass.

## Limitations and security model

This is authorized passive reconnaissance with a conservative GET/HEAD allow policy,
not a guarantee of zero side effects: an application may mutate on GET. Common
logout/delete/reset/purchase-style paths are blocked, but the denylist is incomplete;
use a test environment and explicit exclusions for application-specific actions.

Blocking POST prevents GraphQL POST and other API requests from reaching the server;
their attempts still appear in request observations. No request payload is retained,
so later feature detection must respect that evidence limitation. Blocked external
assets, frames, workers, redirects and WebSockets can prevent SPA rendering or SSO.
This milestone records header presence, not sufficient values for security analysis.
Crawl controls are application-level and do not replace an OS/network sandbox for
hostile browser code. Background Chromium behavior and all browser-native protocols
are not exhaustively modeled. No multi-origin scope, active interactions, HTTPX
fallback, feature detection, ASVS classification, or compliance assertions exist.

## Local tests

`tests/test_crawler_integration.py` contains ephemeral threaded HTTP fixtures. Tests
check server-received requests, not only policy functions: redirects and loops,
external requests, POST/form blocking, frames/popups, WebSocket attempts, rendered
links, cookie authentication, deduplication, rate and request/page/depth/duration
limits, redaction, CLI use, and SQLite round trips. No public web crawling is used.

For managed workspaces with an unwritable browser cache:

```bash
export PLAYWRIGHT_BROWSERS_PATH=/tmp/asvs-browsers
python -m playwright install chromium
python -m pytest -q
```
