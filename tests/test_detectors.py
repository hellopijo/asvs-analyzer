import json
from hashlib import sha256
import pytest
from typer.testing import CliRunner
from asvs_analyzer.cli import app
from asvs_analyzer.detectors.engine import detect_features
from asvs_analyzer.models.crawl import CrawlRun, PageObservation, FormObservation, Observation
from asvs_analyzer.storage.crawls import CrawlStore
from asvs_analyzer.storage.features import FeatureStore


def run(pages=None, observations=None):
    return CrawlRun(target='https://app.test/', scope_path='/', pages=pages or [], observations=observations or [])


def feature(crawl, name):
    return next(f for f in detect_features(crawl).features if f.feature == name)


def obs(kind='request', url='https://app.test/api', **kwargs):
    return Observation(kind=kind, url=url, source_url='https://app.test/', **kwargs)


def page(inputs, enctype='application/x-www-form-urlencoded'):
    return PageObservation(url='https://app.test/', depth=0, forms=[FormObservation(action='https://app.test/action', method='post', enctype=enctype, input_types=inputs)])


def test_empty_crawl_returns_all_five_unknowns():
    results = detect_features(run()).features
    assert len(results) == 5
    assert all(f.status == 'not_observed' and f.confidence == 0 and not f.evidence for f in results)
    assert all('Not observed does not mean absent' in f.limitations[-1] for f in results)


@pytest.mark.parametrize('name,control', [('authentication','password'), ('file_upload','file')])
def test_form_controls(name, control):
    result = feature(run([page([control])]), name)
    assert result.status == 'observed'
    assert result.evidence[0].reference == '/pages/0/forms/0'


def test_multipart_alone_is_weak():
    assert feature(run([page(['text'], 'multipart/form-data')]), 'file_upload').status == 'suspected'


def test_unattached_file_input():
    p = page([])
    p.input_types = ['file']
    assert feature(run([p]), 'file_upload').status == 'observed'


@pytest.mark.parametrize('name,expected', [('session','suspected'), ('__Host-sessionid','suspected'), ('theme','not_observed'), ('session_banner','not_observed')])
def test_cookie_names(name, expected):
    assert feature(run(observations=[obs('cookie', attributes={'name':name})]), 'authentication').status == expected


@pytest.mark.parametrize('scheme', ['basic','bearer','digest','negotiate'])
def test_auth_schemes(scheme):
    result = feature(run(observations=[obs('response', attributes={'www-authenticate':scheme})]), 'authentication')
    assert result.status == 'observed'
    assert scheme in result.evidence[0].summary


def test_auth_route_boundary():
    p = page([])
    p.url = 'https://app.test/login-guide'
    assert feature(run([p]), 'authentication').status == 'not_observed'
    p.links = ['https://app.test/login']
    assert feature(run([p]), 'authentication').status == 'suspected'


@pytest.mark.parametrize('kind,status,expected', [('response',302,'observed'), ('response',200,'not_observed'), ('request',None,'suspected')])
def test_oauth_patterns(kind,status,expected):
    url = 'https://idp.test/authorize?client_id=[REDACTED]&response_type=[REDACTED]&redirect_uri=[REDACTED]'
    result = feature(run(observations=[obs(kind,url=url,status=status,attributes={'location':url})]), 'oauth_oidc')
    assert result.status == expected
    assert 'distinguishing OAuth from OIDC' in result.limitations[0]


def test_oauth_path_alone_is_insufficient():
    assert feature(run(observations=[obs(url='https://app.test/oauth')]), 'oauth_oidc').status == 'not_observed'


def test_blocked_socket_trace():
    item = obs('websocket',url='wss://external.test/socket',blocked_reason='websocket_handshake_disabled')
    result = feature(run(observations=[item]), 'websocket')
    assert result.status == 'observed'
    assert result.evidence[0].observation_id == item.id
    assert 'server support is unconfirmed' in result.evidence[0].summary


@pytest.mark.parametrize('url,mime,expected', [
    ('https://app.test/graphql',None,'suspected'),
    ('https://app.test/graphql-guide',None,'not_observed'),
    ('https://app.test/api','application/graphql','observed'),
    ('https://app.test/api','application/graphql-response+json','observed'),
    ('https://app.test/api?query=[REDACTED]&operationName=[REDACTED]',None,'suspected'),
    ('https://app.test/api?query=[REDACTED]',None,'not_observed'),
])
def test_graphql_rules(url,mime,expected):
    result = feature(run(observations=[obs(url=url,attributes={'content-type':mime} if mime else {})]), 'graphql')
    assert result.status == expected


def test_out_of_scope_request_is_not_graphql_evidence():
    item = obs(url='https://external.test/graphql',blocked_reason='out_of_scope')
    assert feature(run(observations=[item]), 'graphql').status == 'not_observed'


def test_blocked_post_is_only_hint():
    item = obs(url='https://app.test/graphql',method='POST',blocked_reason='unsafe_method')
    result = feature(run(observations=[item]), 'graphql')
    assert result.status == 'suspected'
    assert 'blocked' in result.evidence[0].summary


def test_references_hash_determinism_and_no_mutation():
    crawl = run([page(['file'])], [obs('websocket')])
    before = crawl.model_dump_json()
    a,b = detect_features(crawl),detect_features(crawl)
    assert a.crawl_sha256 == sha256(before.encode()).hexdigest()
    assert crawl.model_dump_json() == before
    for fa,fb in zip(a.features,b.features):
        assert fa.model_dump(exclude={'detected_at'}) == fb.model_dump(exclude={'detected_at'})
        for evidence in fa.evidence:
            node = json.loads(before)
            for part in evidence.reference.strip('/').split('/'):
                node = node[int(part)] if isinstance(node,list) else node[part]
            assert node is not None


def test_coverage_limits_retained():
    crawl = run()
    crawl.stop_reason = 'request_limit'
    crawl.limitations = ['No POST payloads.']
    result = detect_features(crawl)
    assert 'No POST payloads.' in result.limitations
    assert any('request_limit' in text for text in result.limitations)


def test_storage_cli_and_source_unchanged(tmp_path):
    db = tmp_path / 'db.sqlite3'
    crawl = run([page(['file'])])
    CrawlStore(db).save(crawl)
    result = detect_features(crawl)
    store = FeatureStore(db)
    store.save(result)
    assert store.load(result.id) == result
    output = CliRunner().invoke(app,['detect','--run-id',crawl.id,'--db',str(db),'--details'])
    assert output.exit_code == 0, output.output
    assert 'file_upload' in output.output and '/pages/0/forms/0' in output.output
    assert CrawlStore(db).load(crawl.id) == crawl


@pytest.mark.parametrize('exists',[True,False])
def test_cli_missing_crawl(tmp_path,exists):
    db = tmp_path/'db.sqlite3'
    if exists:
        CrawlStore(db).save(run())
    output = CliRunner().invoke(app,['detect','--run-id','missing','--db',str(db)])
    assert output.exit_code == 1
    assert 'Traceback' not in output.output
    assert db.exists() == exists
