"""The library never creates schema: a missing DB file is an error, not a CREATE."""
import pytest

from ampachedata import DatabaseError
from ampachedata.data.db.Database import Database


def testMissingDatabaseFileIsRejected(tmp_path):
    with pytest.raises(DatabaseError):
        Database(str(tmp_path / "nope.db"))
