"""Environment-driven settings with a local-only target guard.

Tests must never reach production systems. Every URL is validated against an allowlist:
loopback hosts plus any names listed in QE_ALLOWED_HOSTS (e.g. docker compose service
names such as "backend").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class UnsafeTargetError(ValueError):
    """Raised when a configured URL points outside the allowed local hosts."""


def allowed_hosts(env: dict[str, str] | None = None) -> frozenset[str]:
    env = os.environ if env is None else env
    extra = {h.strip().lower() for h in env.get("QE_ALLOWED_HOSTS", "").split(",") if h.strip()}
    return LOOPBACK_HOSTS | extra


def validate_local_url(url: str, hosts: frozenset[str]) -> str:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise UnsafeTargetError(f"unsupported scheme in {url!r}; expected http or https")
    host = (parts.hostname or "").lower()
    if host not in hosts:
        raise UnsafeTargetError(
            f"refusing non-local target {host!r} in {url!r}; allowed: {sorted(hosts)} "
            "(extend with QE_ALLOWED_HOSTS only for local containers)"
        )
    return url.rstrip("/")


@dataclass(frozen=True)
class Settings:
    api_url: str
    ui_url: str
    aut_dir: Path

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        env = os.environ if env is None else env
        hosts = allowed_hosts(env)
        aut_dir = Path(env.get("AUT_DIR", PROJECT_ROOT.parent / "git-demo" / "starter_code"))
        return cls(
            api_url=validate_local_url(env.get("AUT_API_URL", "http://localhost:8080"), hosts),
            ui_url=validate_local_url(env.get("AUT_UI_URL", "http://localhost:5173"), hosts),
            aut_dir=aut_dir,
        )
