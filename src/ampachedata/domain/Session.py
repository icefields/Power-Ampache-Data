"""Domain representation of the current Ampache session (read back from SessionEntity)."""
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class Session:
    auth: str                       # session token (32-hex), NOT the password hash
    sessionExpire: str              # ISO 8601, stored verbatim
    api: str
    counts: Mapping[str, int] = field(default_factory=dict)
