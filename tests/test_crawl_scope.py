import pytest
from pydantic import ValidationError
from asvs_analyzer.crawler.scope import Scope, canonical_url, risky_url
from asvs_analyzer.crawler.redaction import Redactor
from asvs_analyzer.models.crawl import CrawlConfig


@pytest.mark.parametrize('url', ['https://example.com/app', 'https://EXAMPLE.com:443/app/page#x', 'https://example.com/app?q=x'])
def test_scope_accepts(url):
    assert Scope('https://example.com/app', '/app').contains(url)


@pytest.mark.parametrize('url', ['http://example.com/app', 'https://example.com:444/app', 'https://example.com.evil/app', 'https://evil.com/app', 'https://example.com/application', 'https://example.com/app/../outside', 'https://example.com/app/%2e%2e/outside', 'https://example.com/app%2f..%2foutside', 'https://example.com/app/%252e%252e/outside', 'https://user:secret@example.com/app', 'https://example.com/app\\outside', 'https://example.com/app/;x', 'file:///app', 'https://example.com/app/%00'])
def test_scope_rejects(url):
    assert not Scope('https://example.com/app', '/app').contains(url)


def test_dedup_identity():
    assert canonical_url('http://EXAMPLE.com:80#one') == canonical_url('http://example.com/#two')
    assert canonical_url('http://example.com/?q=a') != canonical_url('http://example.com/?q=b')


@pytest.mark.parametrize('changes', [{}, {'authorized': True, 'max_pages': 0}, {'authorized': True, 'scope_path': '/other'}, {'authorized': True, 'max_requests': 0}])
def test_config_validation(changes):
    with pytest.raises(ValidationError):
        CrawlConfig(target='https://example.com/app', **changes)


def test_redaction():
    r = Redactor()
    r.remember('secret123')
    value = r.url('https://user:password@example.com/secret123?token=TOPSECRET&state=OAUTHSECRET#ACCESSSECRET')
    for secret in ['user', 'password', 'secret123', 'TOPSECRET', 'OAUTHSECRET', 'ACCESSSECRET']:
        assert secret not in value
    assert 'state=[REDACTED]' in value
    assert r.headers({'authorization': 'Bearer secret', 'set-cookie': 'sid=secret', 'www-authenticate': 'Bearer secret', 'content-security-policy': 'nonce-secret'}) == {'authorization': 'bearer', 'set-cookie': '[PRESENT]', 'www-authenticate': 'bearer', 'content-security-policy': '[PRESENT]'}


@pytest.mark.parametrize('path', ['/logout', '/users/delete/1', '/api?operation=destroy', '/reset-password'])
def test_risky_actions(path):
    assert risky_url('https://example.com' + path)
