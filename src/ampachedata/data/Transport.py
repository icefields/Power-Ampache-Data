# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""The injectable HTTP seam. AmpacheClient depends on Transport, never on urllib."""
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Protocol


class Transport(Protocol):
    """Sends one request, returns the decoded JSON payload. Implementations do NOT
    raise for API error envelopes — error mapping happens in data/errors.py.
    Non-2xx HTTP answers are likewise returned as error envelopes carrying
    the HTTP status as the code, never raised raw — AmpacheClient's silent
    re-auth (401/403) depends on this contract."""

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
        try:
            with urllib.request.urlopen(request, timeout=self._timeoutSeconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            # Non-2xx answers become error envelopes carrying the HTTP status
            # as the code, so raiseForError can map them (401/403 ->
            # InvalidHandshakeError, which drives AmpacheClient's silent
            # re-auth + single retry). A body that already IS a JSON error
            # envelope passes through unchanged — the server's own code wins;
            # spec-shaped envelopes (errorCode/errorMessage keys) are
            # normalized to code/message first. Raw HTTP errors never leak
            # past data/.
            errorBody = error.read().decode("utf-8", "replace")
            try:
                payload = json.loads(errorBody)
            except ValueError:
                payload = None
            if isinstance(payload, dict) and "error" in payload:
                errorObject = payload["error"]
                if (isinstance(errorObject, dict) and "code" not in errorObject
                        and "errorCode" in errorObject):
                    # Spec-shaped envelope: errorCode/errorMessage keys, the
                    # code as a STRING — e.g. HTTP 401 carrying
                    # {'error': {'errorCode': '4701', 'errorMessage':
                    # 'Session Expired'}} on a stale session token. Normalize
                    # to code/message so raiseForError's int() coercion can
                    # map it ('4701' -> InvalidHandshakeError -> silent
                    # re-auth + one retry). The code stays a string here —
                    # raiseForError owns the int coercion.
                    return {
                        "error": {
                            "code": errorObject["errorCode"],
                            "message": errorObject.get("errorMessage") or "",
                        }
                    }
                return payload
            message = errorBody.strip() or str(error.reason)
            if len(message) > 200:
                message = message[:200] + "..."
            return {"error": {"code": error.code, "message": message}}
