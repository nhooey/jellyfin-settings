"""The `jellyfin-settings` command: apply, plan and diff declared settings.

SETTINGS is a JSON file holding:

  {"url": "http://localhost:8096",
   "encoding": {"HardwareAccelerationType": "videotoolbox", ...},
   "users": {"<name>": {"SubtitleMode": "Always", ...}},
   "libraries": {"<name>": {"type": "movies", "paths": ["~/Video/Movies"]}}}

Only the keys listed are changed, and no library or path is removed.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Annotated

import httpx
import typer

from . import jellyfin
from .plan import Plan, plan
from .secrets import read_key

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)

Settings = Annotated[Path, typer.Argument(exists=True, dir_okay=False, help="The settings JSON file.")]
Secretspec = Annotated[str, typer.Option(help="The secretspec command to read the key with.")]
Manifest = Annotated[Path, typer.Option(help="The SecretSpec manifest declaring JELLYFIN_API_KEY.")]
DEFAULT_MANIFEST = Path("~/.config/secretspec/jellyfin.toml").expanduser()


def warn(msg: str) -> None:
    typer.echo(f"jellyfin-settings: {msg}", err=True)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read_stamp(path: Path) -> str | None:
    try:
        return path.read_text().strip()
    except OSError:
        return None


def current_plan(settings: dict, secretspec: str, manifest: Path) -> tuple[Plan, httpx.Client] | str:
    """The plan against the running Jellyfin and a client to send it, or why there's none."""
    url = settings.get("url", "http://localhost:8096").rstrip("/")
    if not jellyfin.answers(url):
        return f"Jellyfin doesn't answer at {url}"
    key = read_key(secretspec, str(manifest))
    if key is None:
        return "couldn't read JELLYFIN_API_KEY through SecretSpec"
    c = jellyfin.client(url, key)
    return plan(jellyfin.read_state(c), settings, os.path.expanduser), c


@app.command()
def apply(
    settings: Settings,
    if_changed: Annotated[
        Path | None,
        typer.Option(
            metavar="STAMP",
            help="Do nothing when STAMP holds the settings' hash; write it after a successful run.",
        ),
    ] = None,
    dry_run: Annotated[bool, typer.Option(help="Print the requests instead of sending them.")] = False,
    secretspec: Secretspec = "secretspec",
    manifest: Manifest = DEFAULT_MANIFEST,
) -> None:
    """Apply the declared settings. Exits 0 when Jellyfin or the key isn't there, to retry later."""
    raw = settings.read_bytes()
    if if_changed and read_stamp(if_changed) == digest(raw):
        return
    found = current_plan(json.loads(raw), secretspec, manifest)
    if isinstance(found, str):
        warn(f"{found}; nothing applied")
        return
    p, c = found
    for s in p.skipped:
        warn(f"{s}; skipped")
    try:
        for note in (
            (f"would {r.method} {r.path}" for r in p.requests) if dry_run else jellyfin.send(c, p.requests)
        ):
            typer.echo(note)
    except httpx.HTTPError as e:
        warn(f"Jellyfin refused a request ({e}); stopped")
        return
    finally:
        c.close()
    if if_changed and not dry_run:
        if_changed.parent.mkdir(parents=True, exist_ok=True)
        if_changed.write_text(digest(raw) + "\n")


@app.command()
def diff(
    settings: Settings,
    secretspec: Secretspec = "secretspec",
    manifest: Manifest = DEFAULT_MANIFEST,
) -> None:
    """Print where Jellyfin differs from the declared settings. Exits 1 on drift, 2 if it can't check."""
    found = current_plan(json.loads(settings.read_bytes()), secretspec, manifest)
    if isinstance(found, str):
        warn(found)
        raise typer.Exit(2)
    p, c = found
    c.close()
    lines = p.drift + tuple(f"{s}; skipped" for s in p.skipped)
    typer.echo("\n".join(lines) if lines else "Jellyfin matches the declared settings")
    raise typer.Exit(1 if lines else 0)


def main() -> None:
    app()
