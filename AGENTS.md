# jellyfin-settings

A Nix flake whose Home Manager module declares Jellyfin's settings, and a Python command,
`jellyfin-settings`, that applies them through Jellyfin's REST API. [README.md](README.md) says what it
does and how it's built.

## Layout

- `src/jellyfin_settings/`: the Python package; `plan.py` is pure, `jellyfin.py` does the HTTP calls,
  `cli.py` is the typer command.
- `tests/`: pytest unit tests, with respx mocking Jellyfin.
- `nix/package.nix`: the package; `nix/home-module.nix`: the Home Manager module.
- `skills-devshell/`: the sub-flake that installs the project's skills into `.agents/skills/` when the
  dev shell starts.

## Build and test

- `nix flake check`: builds the package, which runs the unit tests, and runs ruff's lint and format
  checks.
- In the dev shell (`nix develop`): `tests` runs pytest against the source tree, and `lint` runs ruff.
- `nix fmt`: formats the Nix and Python files.
