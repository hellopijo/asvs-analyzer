"""Minimize captured data: no bodies, cookie values, or query values."""
import re
from urllib.parse import parse_qsl, unquote, urlsplit, urlunsplit

_QUERY_NAMES = {"client_id", "redirect_uri", "response_type", "scope", "state", "nonce", "code", "code_challenge", "code_challenge_method", "query", "operationName", "variables"}


class Redactor:
    def __init__(self) -> None:
        self.secrets: set[str] = set()

    def remember(self, value: str) -> None:
        if value:
            self.secrets.add(value)

    def text(self, value: str) -> str:
        for secret in sorted(self.secrets, key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"[A-Za-z0-9_+./=%@-]{24,}", "[REDACTED]", value)
        value = re.sub(r"[\w.+-]+@[\w.-]+", "[REDACTED]", value)
        return re.sub(r"[\x00-\x1f\x7f]", "", value)[:512]

    def url(self, value: str) -> str:
        try:
            parts = urlsplit(value)
            if parts.scheme not in ("http", "https", "ws", "wss") or not parts.hostname:
                return "[UNSUPPORTED URL]"
            host = parts.hostname
            if ":" in host:
                host = f"[{host}]"
            if parts.port:
                host += f":{parts.port}"
            # Query names are also untrusted; retain only recognized protocol keys.
            query = "&".join(f"{key if key in _QUERY_NAMES else 'parameter'}=[REDACTED]"
                             for key, _ in parse_qsl(parts.query, keep_blank_values=True)[:30])
            path = "/".join(self.text(unquote(segment)) for segment in parts.path.split("/"))
            return urlunsplit((parts.scheme, host, path, query, ""))[:2048]
        except ValueError:
            return "[INVALID URL]"

    def headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Record header presence; allow only tightly validated non-secret values."""
        result = {}
        allowed = {"content-type", "strict-transport-security", "content-security-policy",
                   "x-frame-options", "x-content-type-options", "referrer-policy",
                   "permissions-policy", "access-control-allow-origin", "www-authenticate",
                   "set-cookie", "location", "authorization"}
        for key, value in headers.items():
            key = key.lower()
            if key not in allowed:
                continue
            result[key] = "[PRESENT]"
            if key == "content-type":
                mime = value.split(";", 1)[0].lower().strip()
                if mime in {"text/html", "application/json", "application/graphql", "application/javascript", "text/css", "multipart/form-data"}:
                    result[key] = mime
            elif key == "location":
                result[key] = self.url(value)
            elif key in {"www-authenticate", "authorization"}:
                scheme = value.split(" ", 1)[0].lower()
                if scheme in {"basic", "bearer", "digest", "negotiate"}:
                    result[key] = scheme
        return result
