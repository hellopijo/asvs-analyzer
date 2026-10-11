"""Run a versioned deterministic detector set over an existing crawl snapshot."""
from datetime import UTC, datetime
from hashlib import sha256

from asvs_analyzer.detectors.rules import DETECTORS
from asvs_analyzer.models.crawl import CrawlRun
from asvs_analyzer.models.features import DetectionRun, FeatureDetection

DETECTOR_VERSION = '1.0.0'
LIMITATIONS = {
    'authentication': 'Password controls and session cookie names do not establish successful login or access control.',
    'file_upload': 'Controls indicate possible upload functionality; acceptance and server processing were not tested.',
    'oauth_oidc': 'Redacted scope/response values prevent distinguishing OAuth from OIDC or identifying the exact flow.',
    'websocket': 'Attempts can target third-party services. Handshakes are blocked, so server support is unconfirmed.',
    'graphql': 'Request bodies are unavailable and POST is blocked. Custom endpoint names can hide GraphQL.',
}


def detect_features(crawl: CrawlRun) -> DetectionRun:
    now = datetime.now(UTC)
    results = []
    for name, detector in DETECTORS.items():
        evidence = detector(crawl)
        results.append(FeatureDetection(feature=name,
            status=('observed' if any(e.direct for e in evidence) else 'suspected') if evidence else 'not_observed',
            confidence=max((e.confidence for e in evidence), default=0), evidence=evidence,
            source_url=evidence[0].source_url if evidence else crawl.target, detected_at=now,
            limitations=[LIMITATIONS[name], 'Not observed does not mean absent. No ASVS applicability or vulnerability verdict is assigned.']))
    return DetectionRun(crawl_id=crawl.id,
        crawl_sha256=sha256(crawl.model_dump_json().encode()).hexdigest(),
        detector_version=DETECTOR_VERSION, created_at=now, features=results,
        limitations=[*crawl.limitations, f'Crawl stopped with reason: {crawl.stop_reason}.',
                     'Confidence is a fixed rule strength, not a calibrated probability.',
                     'Page evidence timestamps use crawl start; individual DOM capture times were not recorded.'])
