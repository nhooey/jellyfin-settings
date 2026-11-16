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
lists and other values replace, and a key the defaults don't have, or a
value of another kind than its default, is an error. Keys inside
`encoding` and each user are Jellyfin's own, so they aren't checked
here.
"""

import json
from collections.abc import Mapping
from importlib.resources import files

from toolz import merge_with

LIBRARY_KEYS = frozenset({"type", "paths"})
KINDS = {dict: "a map", list: "a list", str: "a string", type(None): "null"}


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


def kind(value: object) -> str:
    """The JSON kind of value, as a problem names it."""
    return KINDS.get(type(value), type(value).__name__)


def library_problem(name: str, lib: object) -> str | None:
    """Why one library's entry isn't `{"type": <string>, "paths": [<string>, ...]}`, or None."""
    if not isinstance(lib, Mapping) or set(lib) != LIBRARY_KEYS:
        return f"libraries.{name}: needs exactly the keys {', '.join(sorted(LIBRARY_KEYS))}"
    paths = lib["paths"]
    if not isinstance(lib["type"], str) or not (
        isinstance(paths, list) and all(isinstance(p, str) for p in paths)
    ):
        return f"libraries.{name}: type must be a string and paths a list of strings"
    return None


def problems(settings: Mapping, base: Mapping) -> tuple[str, ...]:
    """Why settings doesn't fit base's shape.

    Unknown keys, values of another kind than their default, users that
    aren't maps, and libraries lacking or adding keys or of the wrong kinds.
    """
    unknown = tuple(f"unknown key {k!r}" for k in sorted(set(settings) - set(base)))
    mistyped = tuple(
        f"{k} must be {kind(base[k])}, not {kind(settings[k])}"
        for k in sorted(set(settings) & set(base))
        if not isinstance(settings[k], type(base[k]))
    )
    if mistyped:
        return unknown + mistyped
    users = tuple(
        f"users.{name} must be a map, not {kind(user)}"
        for name, user in sorted(settings.get("users", {}).items())
        if not isinstance(user, Mapping)
    )
    libraries = tuple(
        found
        for found in (library_problem(n, lib) for n, lib in sorted(settings.get("libraries", {}).items()))
        if found is not None
    )
    return unknown + users + libraries


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
