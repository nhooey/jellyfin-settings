"""The Jellyfin API key, read through SecretSpec, never printed."""

import subprocess

REASON = "jellyfin-settings: apply the declared Jellyfin settings"


def read_key(secretspec: str, manifest: str) -> str | None:
    """The key from `secretspec get JELLYFIN_API_KEY`, or None if it can't be read."""
    try:
        out = subprocess.run(
            [secretspec, "--file", manifest, "get", "JELLYFIN_API_KEY", "--reason", REASON],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    key = out.stdout.strip()
    return key if out.returncode == 0 and key else None
