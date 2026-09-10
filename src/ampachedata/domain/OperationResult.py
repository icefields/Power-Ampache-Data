# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Success result type for write methods (goodbye, bookmark_*, playlist_*, ...)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationResult:
    """A write method's success envelope ({"success": ...}).

    Errors never appear here — raiseForError raises a typed ApiError first,
    so a returned OperationResult always represents success."""

    success: bool
    message: str = ""
