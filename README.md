# ASVS Applicability Analyzer

A command-line tool that helps security testers decide which OWASP ASVS requirements
are relevant to a web application.

**Working now:** import ASVS 5.0, crawl an authorized app, and identify evidence of
login, file upload, OAuth/OIDC, WebSockets, and GraphQL.

**Coming next:** connect those features to ASVS requirements, add human review,
and generate an Excel report. The tool does not establish vulnerabilities or compliance.

## Install

Requires Python 3.12 or newer:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,crawl]'
python -m playwright install chromium
```

On Linux, missing browser system libraries can be installed with
`python -m playwright install --with-deps chromium`.

## Try it

Run these from the project directory. Use an application you are authorized to test.

```bash
# Load the bundled official requirements.
asvs-analyzer import-asvs --file data/asvs-5.0.0-en.json

# Crawl your local application. This prints a crawl ID.
asvs-analyzer crawl --target http://localhost:3000 --authorized --max-pages 20

# Replace YOUR_CRAWL_ID with that ID.
asvs-analyzer detect --run-id YOUR_CRAWL_ID

# Show the evidence behind each result.
asvs-analyzer detect --run-id YOUR_CRAWL_ID --details
```

Results are saved locally in `data/asvs.sqlite3`. Use `--db PATH` on commands to
choose a different database. Detection reads the saved crawl; it makes no new requests.

## Understand the results

- **Observed:** direct evidence was captured, such as a file input or WebSocket attempt.
- **Suspected:** there is a hint, such as a `/graphql` endpoint name.
- **Not observed:** no supporting evidence was captured. The feature may still exist.

Confidence describes the strength of the rule, not whether a feature is secure.
Blocked connection attempts do not prove server support. Each result includes
references to its source evidence and the crawl's limitations.

## Useful commands

```bash
asvs-analyzer requirements --level 2
asvs-analyzer crawl --help
asvs-analyzer detect --help
python -m pytest -q
```

Level selection is cumulative. The bundled release contains 70 Level 1 requirements,
253 through Level 2, and 345 through Level 3.

The crawler blocks form submissions, POST requests, and WebSocket handshakes.
GET endpoints can still have side effects: use a test environment and `--exclude-path`
for sensitive routes. Tokens and cookie values are omitted; route names can still
contain sensitive information, so review evidence before sharing it.

More detail: [crawler options and limits](docs/crawler.md),
[feature detection rules](docs/detectors.md), [dataset format](docs/dataset.md),
[architecture](docs/architecture.md), and [project progress](progress_tracker.md).
The official dataset's attribution and license are in [data/README.md](data/README.md).
