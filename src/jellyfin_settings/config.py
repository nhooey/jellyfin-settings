"""The settings: the shipped defaults with a settings file merged over them.

`defaults.json`, next to this module, holds every setting and its
default:

- `url`: Jellyfin's base URL.
- `encoding`: keys of Jellyfin's encoding configuration
  (`/System/Configuration/encoding`) to set; none by default.
- `users`: per Jellyfin user name, keys of that user's configuration to
  set; none by default.
- `libraries`: libraries by name, each `{"type": <collection type>,
  "paths": [<folder>, ...]}`; none by default.

A settings file names only what it changes. Maps merge key by key,
lists and other values replace, and a key the defaults don't have is an
error. Keys inside `encoding` and each user are Jellyfin's own, so they
aren't checked here.
"""

import json
from collections.abc import Mapping
from importlib.resources import files

from toolz import merge_with

LIBRARY_KEYS = frozenset({"type", "paths"})


class SettingsError(ValueError):
    """A settings file that doesn't fit the defaults' shape."""


def defaults_text() -> str:
    return files(__package__).joinpath("defaults.json").read_text()


def defaults() -> dict:
    return json.loads(defaults_text())


def deep_merge(base: Mapping, over: Mapping) -> dict:
    """over merged into base: maps merge by key, recursively; anything else replaces."""
    return merge_with(
        lambda vs: deep_merge(*vs) if len(vs) == 2 and all(isinstance(v, Mapping) for v in vs) else vs[-1],
        base,
        over,
    )


def problems(settings: Mapping, base: Mapping) -> tuple[str, ...]:
    """Why settings doesn't fit base's shape: unknown keys, and libraries lacking or adding keys."""
    unknown = tuple(f"unknown key {k!r}" for k in sorted(set(settings) - set(base)))
    libraries = settings.get("libraries")
    if libraries is None:
        return unknown
    if not isinstance(libraries, Mapping):
        return (*unknown, "libraries must be a map of library names")
    return unknown + tuple(
        f"libraries.{name}: needs exactly the keys {', '.join(sorted(LIBRARY_KEYS))}"
        for name, lib in sorted(libraries.items())
        if not isinstance(lib, Mapping) or set(lib) != LIBRARY_KEYS
    )


def load(raw: bytes) -> dict:
    """The shipped defaults with the settings file's JSON merged over them."""
    settings = json.loads(raw)
    if not isinstance(settings, Mapping):
        raise SettingsError("the settings file must hold a JSON object")
    base = defaults()
    found = problems(settings, base)
    if found:
        raise SettingsError("; ".join(found))
    return deep_merge(base, settings)
