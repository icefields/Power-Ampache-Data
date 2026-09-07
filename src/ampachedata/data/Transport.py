"""The injectable HTTP seam. AmpacheClient depends on Transport, never on urllib."""
import json
import urllib.parse
import urllib.request
from typing import Dict, Protocol


class Transport(Protocol):
    """Sends one request, returns the decoded JSON payload. Implementations do NOT
    raise for API error envelopes — error mapping happens in data/errors.py."""

    def send(self, method: str, url: str, params: Dict[str, str], headers: Dict[str, str]) -> dict:
        ...


class UrllibTransport:
    """Real transport. GET: params in query string. POST/PUT: form-encoded body
    (per CONVENTIONS). Stdlib only."""

    def __init__(self, timeoutSeconds: float = 30.0):
        self._timeoutSeconds = timeoutSeconds

    def send(self, method, url, params, headers):
        method = method.upper()
        if method == "GET":
            query = urllib.parse.urlencode(params)
            fullUrl = url + "?" + query if query else url
            request = urllib.request.Request(fullUrl, headers=dict(headers), method="GET")
        else:
            body = urllib.parse.urlencode(params).encode("utf-8")
            request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
        with urllib.request.urlopen(request, timeout=self._timeoutSeconds) as response:
            return json.loads(response.read().decode("utf-8"))
