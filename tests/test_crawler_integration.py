"""Real Chromium against loopback HTTP servers only; never public targets."""
import asyncio
from collections import Counter
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest
from typer.testing import CliRunner

pytest.importorskip('playwright.async_api')
from asvs_analyzer.crawler.browser import CrawlError, crawl
from asvs_analyzer.models.crawl import CrawlConfig
from asvs_analyzer.storage.crawls import CrawlStore
from asvs_analyzer.cli import app


@contextmanager
def server():
    hits = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            hits.append((self.command, self.path, time.monotonic(), self.headers.get('Cookie', '')))
            self.send_response(200)
            self.end_headers()
        def do_GET(self):
            hits.append((self.command, self.path, time.monotonic(), self.headers.get('Cookie', '')))
            status, headers, body = self.server.routes.get(self.path.split('?')[0], (200, {}, '<p>ok</p>'))
            if self.path == '/slow':
                time.sleep(.4)
            self.send_response(status)
            self.send_header('Content-Type', 'text/html')
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(body.encode())
            except BrokenPipeError:
                pass
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    httpd.routes = {}
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, f'http://127.0.0.1:{httpd.server_port}', hits
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


def execute(target, **kwargs):
    return asyncio.run(crawl(CrawlConfig(target=target, authorized=True, delay_ms=0, settle_ms=150, **kwargs)))


def test_rendered_evidence_and_no_unsafe_egress(tmp_path):
    with server() as (outside, other, external_hits), server() as (local, base, hits):
        local.routes['/app'] = (200, {'Set-Cookie': 'session=COOKIE_SECRET; HttpOnly; SameSite=Lax'}, f'''<title>TITLE_SECRET</title>
        <form action="/app/upload" method="post" enctype="multipart/form-data">
          <input type="file"><input type="password" value="PASSWORD_SECRET"></form>
        <a href="/app/next#one">next</a><a href="/app/next#two">duplicate</a>
        <a href="/app/redirect">redirect</a><a href="/app/local-redirect">local redirect</a>
        <a href="/app/logout">logout</a><a href="/outside">outside path</a>
        <iframe src="/app/frame"></iframe>
        <script>
        document.body.insertAdjacentHTML('beforeend', '<a href="/app/js">rendered</a>');
        fetch('/app/graphql', {{method:'POST', body:'BODY_SECRET'}}).catch(()=>{{}});
        fetch('/app/data?token=QUERY_SECRET').catch(()=>{{}});
        fetch('{other}/leak').catch(()=>{{}});
        fetch('/outside').catch(()=>{{}});
        fetch('/app/api-redirect').catch(()=>{{}});
        new WebSocket('ws://127.0.0.1:{local.server_port}/app/socket?token=WS_SECRET');
        document.forms[0].submit();
        window.open('/app/popup');
        </script>''')
        local.routes['/app/redirect'] = (302, {'Location': other + '/redirect-leak?code=OAUTH_SECRET'}, '')
        local.routes['/app/local-redirect'] = (302, {'Location': '/app/final'}, '')
        local.routes['/app/api-redirect'] = (302, {'Location': other + '/api-leak'}, '')
        run = execute(base + '/app', scope_path='/app', max_depth=3, max_pages=20)
        paths = Counter(h[1].split('?')[0] for h in hits)
        assert not external_hits
        assert all(h[0] == 'GET' for h in hits)
        for path in ['/outside', '/app/logout', '/app/graphql', '/app/upload', '/app/socket', '/app/frame', '/app/popup']:
            assert paths[path] == 0, (path, hits)
        assert paths['/app/next'] == 1
        assert paths['/app/js'] == 1
        assert paths['/app/final'] == 1
        assert run.pages[0].forms[0].input_types == ['file', 'password']
        assert run.pages[0].forms[0].enctype == 'multipart/form-data'
        assert any(o.kind == 'websocket' for o in run.observations)
        assert any(o.status == 302 for o in run.observations)
        assert any(o.blocked_reason == 'out_of_scope' for o in run.observations)
        cookie = next(o for o in run.observations if o.kind == 'cookie')
        assert cookie.attributes['httpOnly'] is True
        store = CrawlStore(tmp_path / 'crawl.sqlite3')
        store.save(run)
        assert store.load(run.id) == run
        stored = (tmp_path / 'crawl.sqlite3').read_bytes()
        for secret in [b'COOKIE_SECRET', b'PASSWORD_SECRET', b'BODY_SECRET', b'QUERY_SECRET', b'WS_SECRET', b'OAUTH_SECRET', b'TITLE_SECRET']:
            assert secret not in stored


@pytest.mark.parametrize('options,expected_pages,expected_stop', [({'max_depth': 0}, 1, 'complete'), ({'max_pages': 2}, 2, 'page_limit'), ({'max_requests': 1}, 1, 'request_limit')])
def test_budgets(options, expected_pages, expected_stop):
    with server() as (local, base, hits):
        local.routes['/'] = (200, {}, '<a href="/two">two</a><a href="/three">three</a>')
        run = execute(base, **options)
        assert len(run.pages) == expected_pages
        assert run.stop_reason == expected_stop
        if 'max_requests' in options:
            assert len(hits) == 1


def test_authenticated_state_and_exclusion(tmp_path):
    with server() as (local, base, hits):
        state = tmp_path / 'state.json'
        state.write_text(json.dumps({'cookies': [{'name': 'session', 'value': 'AUTH_SECRET', 'domain': '127.0.0.1', 'path': '/', 'expires': -1, 'httpOnly': True, 'secure': False, 'sameSite': 'Lax'}], 'origins': []}))
        local.routes['/'] = (200, {}, '<a href="/private">private</a><a href="/omit">omit</a>')
        run = execute(base, storage_state=state, exclude_paths=['/omit'])
        assert len(hits) == 2
        assert all('AUTH_SECRET' in h[3] for h in hits)
        assert 'AUTH_SECRET' not in run.model_dump_json()
        assert str(state) not in run.model_dump_json()


def test_rate_limit():
    with server() as (local, base, hits):
        local.routes['/'] = (200, {}, '<script>fetch("/one");fetch("/two")</script>')
        run = asyncio.run(crawl(CrawlConfig(target=base, authorized=True, delay_ms=100, settle_ms=350)))
        assert run.requests_sent >= 3
        assert all(b[2] - a[2] >= .08 for a, b in zip(hits, hits[1:]))


def test_cli_requires_authorization(tmp_path):
    result = CliRunner().invoke(app, ['crawl', '--target', 'http://127.0.0.1:9', '--db', str(tmp_path / 'unused.sqlite3')])
    assert result.exit_code == 1
    assert '--authorized' in result.output
    assert not (tmp_path / 'unused.sqlite3').exists()


def test_bad_browser_state_does_not_echo_secrets(tmp_path):
    state = tmp_path / 'state.json'
    state.write_text('SECRET_INVALID_STATE')
    with pytest.raises(CrawlError) as error:
        execute('http://127.0.0.1:9', storage_state=state)
    assert 'SECRET_INVALID_STATE' not in str(error.value)


def test_redirect_loop_is_deduplicated():
    with server() as (local, base, hits):
        local.routes['/'] = (302, {'Location': '/second'}, '')
        local.routes['/second'] = (302, {'Location': '/'}, '')
        run = execute(base)
        assert len(hits) == 2
        assert len(run.pages) == 2
        assert all(page.status == 302 for page in run.pages)


def test_duration_limit_cleans_up_browser():
    with server() as (local, base, hits):
        # Use a longer settling window to reliably trigger the whole-run deadline.
        run = asyncio.run(crawl(CrawlConfig(target=base, authorized=True,
            duration_seconds=1, settle_ms=5000, delay_ms=0)))
        assert run.stop_reason == 'duration_limit'
        assert run.finished_at is not None


def test_script_navigation_and_refresh_do_not_escape_scope():
    with server() as (outside, other, external_hits), server() as (local, base, hits):
        local.routes['/'] = (200, {'Refresh': f'0; url={other}/header'},
            f'<meta http-equiv="refresh" content="0;url={other}/meta"><script>location.href="{other}/script"</script>')
        execute(base)
        assert not external_hits


def test_cli_crawl_persists_successfully(tmp_path):
    with server() as (local, base, hits):
        db = tmp_path / 'cli.sqlite3'
        result = CliRunner().invoke(app, ['crawl', '--target', base, '--authorized', '--max-pages', '1', '--db', str(db)])
        assert result.exit_code == 0, result.output
        assert '1 pages' in result.output
        assert db.exists()


@pytest.mark.parametrize('contents', ['[]', 'null', '{"cookies":null}', '{"origins":[{}]}'])
def test_malformed_state_is_a_safe_error(tmp_path, contents):
    state = tmp_path / 'state.json'
    state.write_text(contents)
    with pytest.raises(CrawlError, match='Cannot load browser state'):
        execute('http://127.0.0.1:9', storage_state=state)


def test_request_timeout_is_recorded():
    with server() as (local, base, hits):
        run = execute(base + '/slow', timeout_ms=100)
        assert run.pages[0].errors
        assert run.finished_at is not None
        assert len(hits) <= 1


def test_rate_wait_does_not_send_after_deadline():
    with server() as (local, base, hits):
        local.routes['/'] = (200, {}, '<script>fetch("/late").catch(()=>{})</script>')
        run = asyncio.run(crawl(CrawlConfig(target=base, authorized=True,
            duration_seconds=1, settle_ms=5000, delay_ms=2000)))
        assert run.stop_reason == 'duration_limit'
        assert [h[1] for h in hits] == ['/']
