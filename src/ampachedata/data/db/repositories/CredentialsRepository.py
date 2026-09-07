"""SQL-only access to CredentialsEntity (single row, PK primaryKey).

The password column holds SHA256(password) — the KEY. Cleartext is never stored."""
from ....domain.Credentials import Credentials

CREDENTIALS_PRIMARY_KEY = "credentials"


class CredentialsRepository:
    def __init__(self, database):
        self._database = database

    def getCredentials(self):
        row = self._database.connection.execute(
            "SELECT username, password, authToken, serverUrl FROM CredentialsEntity LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return Credentials(
            username=row["username"],
            passwordHash=row["password"],
            authToken=row["authToken"],
            serverUrl=row["serverUrl"],
        )

    def upsertCredentials(self, credentials: Credentials) -> None:
        # Single-row invariant: DELETE + INSERT in one transaction.
        with self._database.connection:
            self._database.connection.execute("DELETE FROM CredentialsEntity")
            self._database.connection.execute(
                "INSERT INTO CredentialsEntity "
                "(primaryKey, username, password, authToken, serverUrl, multiUserId) "
                "VALUES (?, ?, ?, ?, ?, '')",
                (
                    CREDENTIALS_PRIMARY_KEY,
                    credentials.username,
                    credentials.passwordHash,
                    credentials.authToken,
                    credentials.serverUrl,
                ),
            )
