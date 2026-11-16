#!/usr/bin/env bash
# Ruff's lint and format checks over the package and its tests, run from the
# repository root. Shared by the dev shell's `lint` and `nix flake check`.
set -euo pipefail

ruff check --no-cache src tests
ruff format --no-cache --check src tests
