# Feature detection

`asvs-analyzer detect --run-id ID [--db PATH] [--details]` reads a stored crawl,
returns all five features, and saves a new feature run in SQLite. It makes no
network requests and does not require Playwright to be installed. No ASVS
applicability classifications are assigned in this milestone.

| Feature | Direct observations | Weaker hints |
| --- | --- | --- |
| Authentication | Password form controls; recognized HTTP authentication schemes | Login routes/links; common session cookie names |
| File upload | File inputs, including inputs within forms | Multipart encoding without file inputs |
| OAuth/OIDC | Redirect carrying client_id, response_type, redirect_uri parameter names | Links or requests with those parameter names |
| WebSocket | Connection attempts recorded by the crawler | None |
| GraphQL | GraphQL-specific request/response media types | Exact graphql path segment; query plus operationName parameters |

Rules live in `detectors/rules.py`; the engine aggregates their evidence.
`DETECTOR_VERSION` identifies the rule set. Change it when changing rule behavior.
Confidence is the strongest supporting rule's fixed score, never an inferred
probability or security verdict. Duplicate weak hints cannot accumulate into a
strong observation. No evidence produces `not_observed` with zero confidence.

Each evidence entry has a JSON pointer into the persisted crawl, observation UUID
where available, source URL, endpoint URL, timestamp, fixed summary, and rule score.
Page pointers include indexes into forms/links. Page evidence uses the crawl start
time because individual DOM timestamps are unavailable. Results retain the crawl
ID, SHA-256 of the model's serialized crawl snapshot, detector version, detection
time, and coverage limitations. The hash is not the original dataset-file hash.
`feature_runs` is an additive append-only SQLite table. Repeated detection creates
new result snapshots without modifying the source crawl.

No secret-bearing request bodies or query values are needed. OAuth and OIDC cannot
be distinguished reliably because scope and response-type values are redacted.
Custom session cookie names, passwordless login, and GraphQL at custom paths without
protocol clues may be missed. A password field may be registration or password
change. A session cookie may belong to an anonymous session. Multipart alone does
not prove upload support. Blocked requests and WebSocket attempts prove only that
an attempt occurred. External WebSocket attempts may belong to third-party services;
external blocked HTTP traffic is excluded from authentication/GraphQL evidence.

New crawls normalize relative Location headers before redaction and retain the
GraphQL response media type. Older stored crawls remain readable, but cannot recover
metadata already omitted by an earlier crawler. A fresh crawl may improve evidence.
