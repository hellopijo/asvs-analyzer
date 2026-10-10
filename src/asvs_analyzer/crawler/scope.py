"""Canonical URL scope, separate from browser behavior and stored redaction."""
import re
from urllib.parse import unquote, urlsplit, urlunsplit


def canonical_url(url: str) -> str:
    """Reject ambiguous encodings; normalize origin/default ports and fragments."""
    if len(url) > 8192 or re.search(r"[\s\\\x00-\x1f\x7f]", url):
        raise ValueError("Invalid URL characters or length")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Expected an absolute HTTP(S) URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("Credentials in URLs are not allowed")
    port = parts.port
    host = parts.hostname.encode("idna").decode("ascii").lower()
    if ":" in host:
        host = f"[{host}]"
    if port and port != {"http": 80, "https": 443}[parts.scheme]:
        host += f":{port}"
    path = parts.path or "/"
    decoded = unquote(path, errors="strict")
    if "%" in decoded or "\\" in decoded or "//" in decoded or ";" in decoded:
        raise ValueError("Ambiguous URL path")
    if any(segment in (".", "..") for segment in decoded.split("/")):
        raise ValueError("Dot segments are not allowed")
    if re.search(r"[\x00-\x1f\x7f]", decoded) or re.search(r"%(?:2f|5c)", path, re.I):
        raise ValueError("Encoded path separators or controls are not allowed")
    return urlunsplit((parts.scheme, host, path, parts.query, ""))


class Scope:
    def __init__(self, target: str, path_prefix: str = "/") -> None:
        target = canonical_url(target)
        parts = urlsplit(target)
        self.origin = f"{parts.scheme}://{parts.netloc}"
        if not path_prefix.startswith("/") or "?" in path_prefix or "#" in path_prefix:
            raise ValueError("Scope path must be an absolute path without query or fragment")
        self.prefix = unquote(urlsplit(canonical_url(self.origin + path_prefix)).path).rstrip("/") or "/"
        if not self.contains(target):
            raise ValueError("Target is outside the configured scope path")

    def contains(self, url: str) -> bool:
        try:
            parts = urlsplit(canonical_url(url))
        except (ValueError, UnicodeError):
            return False
        path = unquote(parts.path)
        return (f"{parts.scheme}://{parts.netloc}" == self.origin and
                (self.prefix == "/" or path == self.prefix or path.startswith(self.prefix + "/")))


# A conservative extra guard, not proof that all remaining GET routes are harmless.
_ACTION = re.compile(r"(?:^|[/_\-?&=])(logout|signout|logoff|delete|remove|destroy|drop|reset|revoke|unsubscribe|checkout|purchase|transfer|execute)(?:$|[/_\-?&=])", re.I)


def risky_url(url: str) -> bool:
    return bool(_ACTION.search(unquote(urlsplit(url).path + "?" + urlsplit(url).query)))
