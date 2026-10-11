"""Conservative sequential browser reconnaissance with interception before egress."""
import asyncio
from collections import deque
from datetime import UTC, datetime
import json
import time
from urllib.parse import unquote, urljoin, urlsplit

from playwright.async_api import Error, Route, WebSocketRoute, async_playwright

from asvs_analyzer.crawler.redaction import Redactor
from asvs_analyzer.crawler.scope import Scope, canonical_url, risky_url
from asvs_analyzer.models.crawl import CrawlConfig, CrawlRun, FormObservation, Observation, PageObservation


class CrawlError(RuntimeError):
    """A safe error message for user-facing crawl failures."""


_GUARDS = """(() => {
  document.addEventListener('submit', e => {e.preventDefault(); e.stopImmediatePropagation();}, true);
  HTMLFormElement.prototype.submit = function() {};
  HTMLFormElement.prototype.requestSubmit = function() {};
  window.open = () => null;
  window.Worker = window.SharedWorker = function() { throw new Error('Disabled by crawl policy'); };
  window.RTCPeerConnection = function() { throw new Error('Disabled by crawl policy'); };
  window.webkitRTCPeerConnection = window.RTCPeerConnection;
})()"""
_DOM = """() => ({
  links: [...document.querySelectorAll('a[href]')].slice(0, 1000).map(a => a.href),
  inputs: [...document.querySelectorAll('input')].slice(0, 200).map(i => i.type),
  forms: [...document.forms].slice(0, 100).map(f => ({
    action: f.action, method: f.method, enctype: f.enctype,
    inputs: [...f.querySelectorAll('input')].slice(0, 200).map(i => i.type)
  }))
})"""


async def crawl(config: CrawlConfig) -> CrawlRun:
    """Return only sanitized observations; raw state never leaves this function."""
    scope = Scope(config.target, config.scope_path)
    redactor = Redactor()
    state = None
    if config.storage_state:
        try:
            with config.storage_state.open('rb') as stream:
                raw = stream.read(5 * 1024 * 1024 + 1)
            if len(raw) > 5 * 1024 * 1024:
                raise ValueError()
            state = json.loads(raw)
            if not isinstance(state, dict) or not isinstance(state.get('cookies', []), list) or not isinstance(state.get('origins', []), list):
                raise ValueError()
            # Import only same-origin local storage and in-scope cookies.
            state['origins'] = [o for o in state.get('origins', []) if o['origin'] == scope.origin]
            host = urlsplit(config.target).hostname
            state['cookies'] = [c for c in state.get('cookies', []) if c['domain'].lstrip('.') == host]
            for cookie in state['cookies']:
                redactor.remember(cookie['value'])
            for origin in state['origins']:
                for item in origin.get('localStorage', []):
                    redactor.remember(item['value'])
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            raise CrawlError('Cannot load browser state; expected a valid Playwright storage-state JSON file') from None
    run = CrawlRun(target=redactor.url(config.target), scope_path=redactor.text(config.scope_path),
                   limits={k: getattr(config, k) for k in ('max_depth', 'max_pages', 'max_requests', 'timeout_ms', 'duration_seconds', 'delay_ms', 'settle_ms')},
                   limitations=[
                       'Read-only reconnaissance is not vulnerability or compliance verification.',
                       'No form submission, POST traffic, WebSocket handshakes, frames, popups, workers, or WebRTC.',
                       'Redirects are intercepted without following; allowed document destinations are queued.',
                       'Only same-origin and configured path requests are sent; excluded resources may prevent rendering.',
                       'GET routes may still mutate state; use only authorized test environments and explicit exclusions.',
                       'No response bodies, title text, input values, cookie values, or query values are retained.',
                       'DOM capture limited to 1000 links, 100 forms, and 200 inputs per page/form.',
                       'Fixed rendering wait and finite budgets cannot establish feature absence.',
                   ])
    queue: deque[tuple[str, int]] = deque()
    seen: set[str] = set()
    intended = ''
    current_depth = 0
    current_page = None
    active = True
    lock = asyncio.Lock()
    last_sent = 0.0
    deadline = float('inf')
    pending_routes: set[Route] = set()
    record_cap = config.max_requests * 3 + config.max_pages * 20

    def excluded(url: str) -> bool:
        path = unquote(urlsplit(url).path)
        return risky_url(url) or any(path == p.rstrip('/') or path.startswith(p.rstrip('/') + '/') for p in config.exclude_paths)

    def enqueue(url: str, depth: int) -> None:
        if depth > config.max_depth:
            return
        try:
            url = canonical_url(url)
        except (ValueError, UnicodeError):
            return
        if url not in seen and scope.contains(url) and not excluded(url):
            if len(seen) >= config.max_pages * 20:
                if 'Discovery queue limit reached.' not in run.limitations:
                    run.limitations.append('Discovery queue limit reached.')
                return
            seen.add(url)
            queue.append((url, depth))

    def record(**kwargs) -> None:
        if len(run.observations) < record_cap:
            run.observations.append(Observation(**kwargs))
        elif 'Observation record limit reached.' not in run.limitations:
            run.limitations.append('Observation record limit reached.')

    async def intercept(route: Route) -> None:
        pending_routes.add(route)
        try:
            await handle_route(route)
        except Error:
            # Closing a page can invalidate an already handled route.
            pass
        finally:
            pending_routes.discard(route)

    async def cancel_pending_routes() -> None:
        routes = list(pending_routes)
        pending_routes.clear()
        await asyncio.gather(*(route.abort() for route in routes), return_exceptions=True)

    async def handle_route(route: Route) -> None:
        nonlocal last_sent
        request = route.request
        async with lock:
            if route not in pending_routes:
                return
            reason = None
            if not active:
                reason = 'crawl_finished'
            elif time.monotonic() >= deadline:
                reason = 'duration_limit'
            elif not scope.contains(request.url):
                reason = 'out_of_scope'
            elif excluded(request.url):
                reason = 'excluded_action_or_path'
            elif request.method not in ('GET', 'HEAD'):
                reason = 'unsafe_method'
            elif request.is_navigation_request() and (request.frame != current_page.main_frame or canonical_url(request.url) != intended):
                reason = 'unscheduled_navigation'
            elif run.requests_sent >= config.max_requests:
                reason = 'request_limit'
            record(kind='request', source_url=redactor.url(intended), url=redactor.url(request.url),
                   method=request.method if request.method in ('GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS') else 'OTHER',
                   blocked_reason=reason,
                   attributes={'resource_type': request.resource_type, **redactor.headers(request.headers)})
            if reason:
                await route.abort()
                return
            await asyncio.sleep(max(0, config.delay_ms / 1000 - (time.monotonic() - last_sent)))
            if route not in pending_routes:
                return
            if not active or time.monotonic() >= deadline:
                await route.abort()
                return
            last_sent = time.monotonic()
            run.requests_sent += 1
            response = None
            try:
                # Browser routing alone can miss redirect hops. Fetch zero hops and
                # inspect Location ourselves; never fulfill a redirect to the browser.
                response = await route.fetch(max_redirects=0, max_retries=0, timeout=config.timeout_ms)
                for cookie in await context.cookies():
                    redactor.remember(cookie['value'])
                headers = dict(response.headers)
                if 'location' in headers:
                    headers['location'] = urljoin(request.url, headers['location'])
                record(kind='response', source_url=redactor.url(intended), url=redactor.url(request.url),
                       status=response.status, attributes=redactor.headers(headers))
                if 300 <= response.status < 400 and 'location' in headers:
                    destination = urljoin(request.url, headers['location'])
                    if request.is_navigation_request():
                        enqueue(destination, current_depth + 1)
                    await route.abort()
                elif 'attachment' in headers.get('content-disposition', '').lower():
                    await route.abort()
                else:
                    # Block browser-initiated refresh and speculative Link fetches.
                    safe_headers = {k: v for k, v in headers.items() if k not in ('refresh', 'link')}
                    await route.fulfill(response=response, headers=safe_headers)
            except Error:
                record(kind='response', source_url=redactor.url(intended), url=redactor.url(request.url),
                       blocked_reason='request_failed')
                try:
                    await route.abort()
                except Error:
                    pass
            finally:
                if response is not None:
                    await response.dispose()

    async def websocket(ws: WebSocketRoute) -> None:
        record(kind='websocket', source_url=redactor.url(intended), url=redactor.url(ws.url),
               blocked_reason='websocket_handshake_disabled')
        await ws.close()

    enqueue(config.target, 0)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(args=['--disable-background-networking', '--disable-quic'])
            try:
                context = await browser.new_context(storage_state=state, service_workers='block', accept_downloads=False)
                await context.route('**/*', intercept)
                await context.route_web_socket('**/*', websocket)
                await context.add_init_script(_GUARDS)
                try:
                    deadline = time.monotonic() + config.duration_seconds
                    async with asyncio.timeout(config.duration_seconds):
                        while queue and len(run.pages) < config.max_pages and run.requests_sent < config.max_requests:
                            intended, current_depth = queue.popleft()
                            current_page = await context.new_page()
                            current_page.set_default_timeout(config.timeout_ms)
                            page_result = PageObservation(url=redactor.url(intended), depth=current_depth)
                            run.pages.append(page_result)
                            try:
                                response = await current_page.goto(intended, wait_until='domcontentloaded', timeout=config.timeout_ms)
                                if response:
                                    page_result.status = response.status
                                await current_page.wait_for_timeout(config.settle_ms)
                                dom = await current_page.evaluate(_DOM)
                                page_result.input_types = dom['inputs']
                                for form in dom['forms']:
                                    page_result.forms.append(FormObservation(action=redactor.url(form['action']),
                                        method=form['method'], enctype=form['enctype'], input_types=form['inputs']))
                                for url in dom['links']:
                                    page_result.links.append(redactor.url(url))
                                    enqueue(url, current_depth + 1)
                            except Error:
                                page_result.errors.append('Navigation or DOM inspection failed/blocked; inspect network observations.')
                                statuses = [o.status for o in run.observations if o.kind == 'response' and o.url == page_result.url and o.status]
                                if statuses:
                                    page_result.status = statuses[-1]
                            finally:
                                await cancel_pending_routes()
                                await current_page.close()
                        if run.requests_sent >= config.max_requests:
                            run.stop_reason = 'request_limit'
                        elif queue:
                            run.stop_reason = 'page_limit'
                except TimeoutError:
                    run.stop_reason = 'duration_limit'
                finally:
                    active = False
                for cookie in (await context.cookies())[:1000]:
                    record(kind='cookie', source_url=run.target, url=run.target, attributes={
                        'name': redactor.text(cookie['name']), 'domain': redactor.text(cookie['domain']),
                        'path': redactor.text(cookie['path']), 'secure': cookie['secure'], 'httpOnly': cookie['httpOnly'],
                        'sameSite': cookie['sameSite'], 'expires': cookie['expires'], 'value': '[REDACTED]'})
                await context.close()
            finally:
                await browser.close()
    except Error:
        raise CrawlError('Browser crawl failed; install Chromium with playwright install chromium and check browser state/runtime dependencies') from None
    # Final pass catches cookie/local-storage secrets learned after early records.
    for page in run.pages:
        page.url = redactor.url(page.url)
        page.links = [redactor.url(url) for url in page.links]
        for form in page.forms:
            form.action = redactor.url(form.action)
    for observation in run.observations:
        observation.url = redactor.url(observation.url)
        observation.source_url = redactor.url(observation.source_url)
    run.finished_at = datetime.now(UTC)
    return run
