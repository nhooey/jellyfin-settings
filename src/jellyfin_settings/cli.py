"""The `jellyfin-settings` command: apply and diff declared settings.

SETTINGS is a JSON file naming only what it changes from the shipped
defaults (`jellyfin-settings config show --defaults`), such as:

  {"url": "http://media.local:8096",
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

from . import config, jellyfin
from .plan import Plan, plan
from .secrets import read_key

app = typer.Typer(no_args_is_help=True, add_completion=False, help=__doc__)
config_app = typer.Typer(no_args_is_help=True, help="Show the settings in effect.")
app.add_typer(config_app, name="config")

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


def read_settings(raw: bytes) -> dict:
    """The settings in effect, or exit 2 saying why the file doesn't fit."""
    try:
        return config.load(raw)
    except ValueError as e:
        warn(f"bad settings: {e}")
        raise typer.Exit(2) from e


def current_plan(settings: dict, secretspec: str, manifest: Path) -> tuple[Plan, httpx.Client] | str:
    """The plan against the running Jellyfin and a client to send it, or why there's none."""
    url = settings["url"].rstrip("/")
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
    """Apply the declared settings.

    Exits 0 when Jellyfin or the key isn't there, to retry later, and 2 on bad settings.
    """
    raw = settings.read_bytes()
    if if_changed and read_stamp(if_changed) == digest(raw):
        return
    found = current_plan(read_settings(raw), secretspec, manifest)
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
    found = current_plan(read_settings(settings.read_bytes()), secretspec, manifest)
    if isinstance(found, str):
        warn(found)
        raise typer.Exit(2)
    p, c = found
    c.close()
    lines = p.drift + tuple(f"{s}; skipped" for s in p.skipped)
    typer.echo("\n".join(lines) if lines else "Jellyfin matches the declared settings")
    raise typer.Exit(1 if lines else 0)


@config_app.command()
def show(
    settings: Annotated[
        Path | None, typer.Argument(exists=True, dir_okay=False, help="The settings JSON file.")
    ] = None,
    defaults: Annotated[bool, typer.Option(help="Print the shipped defaults file.")] = False,
) -> None:
    """Print the settings in effect: SETTINGS merged over the shipped defaults."""
    if defaults or settings is None:
        typer.echo(config.defaults_text(), nl=False)
        return
    typer.echo(json.dumps(read_settings(settings.read_bytes()), indent=2))


def main() -> None:
    app()
