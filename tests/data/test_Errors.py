# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""raiseForError envelope parsing: classic code/message shape, spec-shaped
errorCode/errorMessage envelopes (HTTP 200 handshake rejections), and the
non-dict fallback."""
import pytest

from ampachedata.data.errors import (
    AccessDeniedError,
    BadRequestError,
    DeprecatedError,
    InvalidHandshakeError,
    NotFoundError,
    UnknownApiError,
    raiseForError,
)


def testSuccessPayloadsAreNoOps():
    raiseForError({})
    raiseForError({"auth": "abc123"})
    raiseForError({"error": None})


@pytest.mark.parametrize("payload,expectedType,expectedCode", [
    ({"error": {"code": 4701, "message": "Session Expired"}}, InvalidHandshakeError, 4701),
    ({"error": {"code": "4701", "message": "Session Expired"}}, InvalidHandshakeError, 4701),
    ({"error": {"code": 401, "message": "Unauthorized"}}, InvalidHandshakeError, 401),
    ({"error": {"code": 403, "message": "Forbidden"}}, InvalidHandshakeError, 403),
    ({"error": {"code": 4703, "message": "Access Denied"}}, AccessDeniedError, 4703),
    ({"error": {"code": 4704, "message": "Not Found"}}, NotFoundError, 4704),
    ({"error": {"code": 4706, "message": "Deprecated"}}, DeprecatedError, 4706),
    ({"error": {"code": 4710, "message": "Bad Request"}}, BadRequestError, 4710),
    ({"error": {"code": 4999, "message": "Unmapped"}}, UnknownApiError, 4999),
])
def testCodeMessageShapesMapExactlyAsBefore(payload, expectedType, expectedCode):
    with pytest.raises(expectedType) as excInfo:
        raiseForError(payload)
    assert excInfo.value.code == expectedCode
    assert excInfo.value.message == payload["error"]["message"]


def testNonDictErrorKeepsCodeZeroAndStringifiedMessage():
    with pytest.raises(UnknownApiError) as excInfo:
        raiseForError({"error": "plain string failure"})
    assert excInfo.value.code == 0
    assert excInfo.value.message == "plain string failure"


def testCapturedHandshakeRejectionEnvelopeMapsToInvalidHandshake():
    """Exact envelope captured from a live server: HTTP 200 response to a
    handshake with an unsupported version."""
    payload = {
        "error": {
            "errorCode": "4701",
            "errorAction": "handshake",
            "errorType": "version",
            "errorMessage": "Received Invalid Handshake",
        }
    }
    with pytest.raises(InvalidHandshakeError) as excInfo:
        raiseForError(payload)
    assert excInfo.value.code == 4701
    assert excInfo.value.message == "Received Invalid Handshake"


def testSpecShapedEnvelopeWithUnmappedCodeRaisesUnknown():
    payload = {
        "error": {
            "errorCode": "4999",
            "errorAction": "handshake",
            "errorType": "mystery",
            "errorMessage": "Something Without A Mapping",
        }
    }
    with pytest.raises(UnknownApiError) as excInfo:
        raiseForError(payload)
    assert excInfo.value.code == 4999
    assert excInfo.value.message == "Something Without A Mapping"


def testCodeKeyWinsWhenBothShapesPresent():
    payload = {
        "error": {
            "code": 4704,
            "message": "Not Found",
            "errorCode": "4701",
            "errorMessage": "Received Invalid Handshake",
        }
    }
    with pytest.raises(NotFoundError) as excInfo:
        raiseForError(payload)
    assert excInfo.value.code == 4704
    assert excInfo.value.message == "Not Found"
