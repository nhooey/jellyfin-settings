"""What to change in Jellyfin, as pure functions.

`plan` maps what Jellyfin holds and what is declared to a `Plan`: the
drift found, the requests that remove it, and the declared things that
can't be applied. Nothing here reads or writes anything; `jellyfin.py`
and `cli.py` do the I/O.
"""

from collections.abc import Callable, Mapping
from typing import Any, NamedTuple
from urllib.parse import urlencode

from toolz import concat, itemfilter, merge


class Request(NamedTuple):
    """One API request, and what it does in a few words."""

    method: str
    path: str
    body: Any
    note: str


class Plan(NamedTuple):
    drift: tuple[str, ...] = ()
    requests: tuple[Request, ...] = ()
    skipped: tuple[str, ...] = ()


def join(*plans: Plan) -> Plan:
    """The plans' drift, requests and skips, in order."""
    return Plan(*(tuple(concat(p[i] for p in plans)) for i in range(len(Plan._fields))))


def changed(current: Mapping, wanted: Mapping) -> dict:
    """The wanted keys whose value differs from current's."""
    return itemfilter(lambda kv: current.get(kv[0]) != kv[1], wanted)


def config_plan(label: str, current: Mapping, wanted: Mapping, path: str) -> Plan:
    """Drift in one configuration, and the one POST that sets it whole."""
    diff = changed(current, wanted)
    keys = sorted(diff)
    return Plan(
        drift=tuple(f"{label}.{k}: Jellyfin has {current.get(k)!r}, declared {diff[k]!r}" for k in keys),
        requests=(Request("POST", path, merge(current, diff), f"{label}: set {', '.join(keys)}"),)
        if diff
        else (),
    )


def users_plan(users: list[Mapping], wanted: Mapping) -> Plan:
    """The plan for each declared user Jellyfin has, found by name."""
    by_name = {u["Name"]: u for u in users}
    return join(
        *(
            config_plan(
                f"users.{name}",
                by_name[name]["Configuration"],
                settings,
                f"/Users/{by_name[name]['Id']}/Configuration",
            )
            if name in by_name
            else Plan(skipped=(f"users.{name}: no such Jellyfin user",))
            for name, settings in sorted(wanted.items())
        )
    )


def library_plan(name: str, lib: Mapping, existing: Mapping, expand: Callable[[str], str]) -> Plan:
    paths = tuple(map(expand, lib["paths"]))
    if name not in existing:
        query = urlencode({"name": name, "collectionType": lib["type"], "refreshLibrary": "false"})
        body = {"LibraryOptions": {"PathInfos": [{"Path": p} for p in paths]}}
        return Plan(
            drift=(f"libraries.{name}: missing in Jellyfin",),
            requests=(Request("POST", f"/Library/VirtualFolders?{query}", body, f"library {name}: added"),),
        )
    missing = tuple(p for p in paths if p not in existing[name])
    return Plan(
        drift=tuple(f"libraries.{name}: lacks path {p}" for p in missing),
        requests=tuple(
            Request(
                "POST",
                "/Library/VirtualFolders/Paths?refreshLibrary=false",
                {"Name": name, "PathInfo": {"Path": p}},
                f"library {name}: added path {p}",
            )
            for p in missing
        ),
    )


def libraries_plan(folders: list[Mapping], wanted: Mapping, expand: Callable[[str], str]) -> Plan:
    """The plan for the declared libraries, then one scan if any changed."""
    existing = {f["Name"]: f.get("Locations", []) for f in folders}
    found = join(*(library_plan(name, lib, existing, expand) for name, lib in sorted(wanted.items())))
    scan = (Request("POST", "/Library/Refresh", None, "libraries: scan started"),) if found.requests else ()
    return found._replace(requests=found.requests + scan)


def plan(state: Mapping, settings: Mapping, expand: Callable[[str], str]) -> Plan:
    """Everything to change, from Jellyfin's state and the declared settings."""
    return join(
        config_plan(
            "encoding", state["encoding"], settings.get("encoding", {}), "/System/Configuration/encoding"
        ),
        users_plan(state["users"], settings.get("users", {})),
        libraries_plan(state["folders"], settings.get("libraries", {}), expand),
    )
