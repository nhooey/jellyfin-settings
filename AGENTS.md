# jellyfin-settings

A Nix flake whose Home Manager module declares Jellyfin's settings, and a Python command,
`jellyfin-settings`, that applies them through Jellyfin's REST API. [README.md](README.md) says what it
does and how it's built.

## Layout

- `src/jellyfin_settings/`: the Python package; `plan.py` is pure, `jellyfin.py` does the HTTP calls,
  `cli.py` is the typer command.
- `tests/`: pytest unit tests, with respx mocking Jellyfin.
- `nix/package.nix`: the package; `nix/home-module.nix`: the Home Manager module;
  `nix/tests/home-module.nix`: its evaluation check.
- `scripts/`: shell scripts the dev shell and `nix flake check` run.
- `skills-devshell/`: the sub-flake that installs the project's skills into `.agents/skills/` when the
  dev shell starts.

## Build and test

`nix develop` enters the dev shell, and `menu` there lists its commands:

- `check`: `nix flake check`, which builds the package, which runs the unit tests, evaluates the Home
  Manager module against stubbed Home Manager options, and runs ruff's lint and format checks.
- `tests`: pytest against the source tree; arguments pass through to pytest.
- `lint`: ruff's lint and format checks, `scripts/lint.sh`, which `nix flake check` also runs.
- `fmt`: formats the Nix and Python files.
- `jellyfin-settings`: the command, run from the source tree.
