"""Explicit feature evidence rules. No network calls or ASVS keyword mapping."""
from collections.abc import Callable
from urllib.parse import parse_qsl, urlsplit

from asvs_analyzer.models.crawl import CrawlRun
from asvs_analyzer.models.features import Evidence


def segments(url: str) -> set[str]:
    return set(urlsplit(url).path.lower().strip('/').split('/'))


def page_evidence(run: CrawlRun, index: int, suffix: str, summary: str,
                  score: float, direct: bool = False) -> Evidence:
    return Evidence(reference=f'/pages/{index}{suffix}', source_url=run.pages[index].url,
                    url=run.pages[index].url, timestamp=run.started_at, summary=summary, confidence=score, direct=direct)


def network_evidence(run: CrawlRun, index: int, summary: str,
                     score: float, direct: bool = False) -> Evidence:
    item = run.observations[index]
    if item.blocked_reason:
        summary += ' The attempt was blocked; server support is unconfirmed.'
    return Evidence(reference=f'/observations/{index}', observation_id=item.id,
                    source_url=item.source_url, url=item.url, timestamp=item.timestamp,
                    summary=summary, confidence=score, direct=direct)


def authentication(run: CrawlRun) -> list[Evidence]:
    found = []
    login_routes = {'login', 'signin', 'sign-in', 'log-in', 'authenticate'}
    for i, page in enumerate(run.pages):
        for j, form in enumerate(page.forms):
            if 'password' in form.input_types:
                found.append(page_evidence(run, i, f'/forms/{j}',
                    'A password input is present; this may be login, registration, or password change.', .8, True))
        if segments(page.url) & login_routes:
            found.append(page_evidence(run, i, '/url', 'An authentication-related route was visited.', .5))
        for j, link in enumerate(page.links):
            if segments(link) & login_routes:
                found.append(page_evidence(run, i, f'/links/{j}', 'A link points to an authentication-related route.', .4))
    session_names = {'session', 'sessionid', 'sid', 'jsessionid', 'phpsessid', 'asp.net_sessionid', 'connect.sid'}
    for i, item in enumerate(run.observations):
        if item.blocked_reason == 'out_of_scope':
            continue
        if item.kind == 'cookie' and str(item.attributes.get('name', '')).lower().removeprefix('__host-').removeprefix('__secure-') in session_names:
            found.append(network_evidence(run, i, 'A cookie has a common session name; anonymous sessions are possible.', .45))
        for header in ('www-authenticate', 'authorization'):
            if item.kind in ('request', 'response') and item.attributes.get(header) in ('basic', 'bearer', 'digest', 'negotiate'):
                found.append(network_evidence(run, i, f'An HTTP {item.attributes[header]} authentication scheme was observed.', .9, True))
    return found


def file_upload(run: CrawlRun) -> list[Evidence]:
    found = []
    for i, page in enumerate(run.pages):
        if 'file' in page.input_types:
            found.append(page_evidence(run, i, '/input_types', 'A file input is present; no file was submitted.', .95, True))
        for j, form in enumerate(page.forms):
            if 'file' in form.input_types:
                found.append(page_evidence(run, i, f'/forms/{j}', 'A form contains a file input; no upload was attempted.', .95, True))
            elif form.enctype.lower() == 'multipart/form-data':
                found.append(page_evidence(run, i, f'/forms/{j}', 'A multipart form is present; multipart alone does not prove file upload.', .55))
    return found


def authorization_pattern(url: str) -> bool:
    names = {key for key, _ in parse_qsl(urlsplit(url).query, keep_blank_values=True)}
    return {'client_id', 'response_type', 'redirect_uri'} <= names


def oauth_oidc(run: CrawlRun) -> list[Evidence]:
    found = []
    for i, page in enumerate(run.pages):
        for j, link in enumerate(page.links):
            if authorization_pattern(link):
                found.append(page_evidence(run, i, f'/links/{j}', 'A link has OAuth authorization parameter names; values are redacted.', .65))
    for i, item in enumerate(run.observations):
        location = item.attributes.get('location')
        if item.kind == 'response' and item.status in (301, 302, 303, 307, 308) and isinstance(location, str) and authorization_pattern(location):
            found.append(network_evidence(run, i, 'An authorization redirect has OAuth parameter names; completion was not tested.', .9, True))
        elif item.kind == 'request' and authorization_pattern(item.url):
            found.append(network_evidence(run, i, 'An attempted authorization request has OAuth parameter names.', .7))
    return found


def websocket(run: CrawlRun) -> list[Evidence]:
    return [network_evidence(run, i, 'A WebSocket connection attempt was observed.', .95, True)
            for i, item in enumerate(run.observations) if item.kind == 'websocket']


def graphql(run: CrawlRun) -> list[Evidence]:
    found = []
    for i, item in enumerate(run.observations):
        if item.kind not in ('request', 'response') or item.blocked_reason == 'out_of_scope':
            continue
        mime = item.attributes.get('content-type')
        names = {key for key, _ in parse_qsl(urlsplit(item.url).query, keep_blank_values=True)}
        if mime in ('application/graphql', 'application/graphql-response+json'):
            found.append(network_evidence(run, i, 'Traffic declares a GraphQL-specific media type.', .9, True))
        elif {'query', 'operationName'} <= names:
            found.append(network_evidence(run, i, 'Traffic has GraphQL-style query and operationName parameters; payload is unavailable.', .7))
        elif 'graphql' in segments(item.url):
            found.append(network_evidence(run, i, 'An observed endpoint has a graphql path segment; the name alone is inconclusive.', .5))
    return found


DETECTORS: dict[str, Callable[[CrawlRun], list[Evidence]]] = {
    'authentication': authentication,
    'file_upload': file_upload,
    'oauth_oidc': oauth_oidc,
    'websocket': websocket,
    'graphql': graphql,
}
