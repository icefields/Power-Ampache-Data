"""Result of ping (health check / expiry probe)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PingResult:
    authenticated: bool
    auth: str = ""
    sessionExpire: str = ""
    api: str = ""
    server: str = ""
    version: str = ""
    compatible: str = ""
