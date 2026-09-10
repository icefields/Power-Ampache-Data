# SPDX-FileCopyrightText: 2026 icefields
# SPDX-License-Identifier: GPL-3.0-only
"""Public API surface guard: every name in __all__ must resolve."""
import ampachedata


def testPublicApiExportsResolve():
    for name in ampachedata.__all__:
        assert getattr(ampachedata, name, None) is not None, name
    for name in (
        "Database",
        "ArtistRepository",
        "AlbumRepository",
        "SongRepository",
        "PlaylistRepository",
    ):
        assert name in ampachedata.__all__
