"""Domain representation of CredentialsEntity. passwordHash is SHA256(password) —
the KEY. Cleartext never exists in this system."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Credentials:
    username: str
    passwordHash: str
    authToken: str
    serverUrl: str
