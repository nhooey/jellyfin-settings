"""Jellyfin's REST API: reading its state and sending a plan's requests."""

from collections.abc import Iterable

import httpx

from .plan import Request


def answers(url: str) -> bool:
    """Whether Jellyfin answers at url, without a key."""
    try:
        return httpx.get(f"{url}/System/Info/Public", timeout=5).is_success
    except httpx.HTTPError:
        return False


def client(url: str, key: str) -> httpx.Client:
    return httpx.Client(
        base_url=url,
        headers={"Authorization": f'MediaBrowser Token="{key}"'},
        timeout=60,
    )


def get(c: httpx.Client, path: str):
    return c.get(path).raise_for_status().json()


def read_state(c: httpx.Client) -> dict:
    """The parts of Jellyfin's state that settings can declare."""
    return {
        "encoding": get(c, "/System/Configuration/encoding"),
        "users": get(c, "/Users"),
        "folders": get(c, "/Library/VirtualFolders"),
    }


def send(c: httpx.Client, requests: Iterable[Request]) -> Iterable[str]:
    """Send each request in order, yielding its note once it succeeds."""
    for r in requests:
        c.request(r.method, r.path, json=r.body).raise_for_status()
        yield r.note
