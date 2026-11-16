"""`python -m jellyfin_settings`, as the dev shell's `jellyfin-settings` runs it from the source tree."""

from jellyfin_settings.cli import app

app(prog_name="jellyfin-settings")
