"""The command against a mocked Jellyfin and a stub secretspec."""

import json
import stat

import httpx
import pytest
import respx
from typer.testing import CliRunner

from jellyfin_settings.cli import app

URL = "http://jellyfin.test"
STATE = {
    "/System/Configuration/encoding": {"H264Crf": 23},
    "/Users": [{"Name": "u", "Id": "42", "Configuration": {"SubtitleMode": "Default"}}],
    "/Library/VirtualFolders": [],
}


@pytest.fixture
def files(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"url": URL, "encoding": {"H264Crf": 20}}))
    stub = tmp_path / "secretspec"
    stub.write_text("#!/bin/sh\necho test-key\n")
    stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
    return settings, str(stub), tmp_path / "stamp"


def mock_jellyfin(mock):
    mock.get(f"{URL}/System/Info/Public").respond(200, json={})
    for path, body in STATE.items():
        mock.get(f"{URL}{path}").respond(200, json=body)
    return mock.post(f"{URL}/System/Configuration/encoding").respond(204)


def run(*args):
    return CliRunner().invoke(app, list(map(str, args)))


def test_apply_posts_with_the_key_and_writes_the_stamp(files):
    settings, stub, stamp = files
    with respx.mock as mock:
        post = mock_jellyfin(mock)
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert r.exit_code == 0, r.output
    assert post.calls.last.request.headers["Authorization"] == 'MediaBrowser Token="test-key"'
    assert json.loads(post.calls.last.request.content) == {"H264Crf": 20}
    assert stamp.read_text().strip()


def test_apply_with_matching_stamp_contacts_nothing(files):
    settings, stub, stamp = files
    with respx.mock as mock:
        mock_jellyfin(mock)
        run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert (r.exit_code, route.called) == (0, False)


def test_apply_without_jellyfin_exits_0_and_writes_no_stamp(files):
    settings, stub, stamp = files
    with respx.mock as mock:
        mock.get(f"{URL}/System/Info/Public").mock(side_effect=httpx.ConnectError("down"))
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert r.exit_code == 0
    assert "doesn't answer" in r.output
    assert not stamp.exists()


def test_diff_reports_drift_with_exit_1_and_sends_nothing(files):
    settings, stub, _ = files
    with respx.mock as mock:
        post = mock_jellyfin(mock)
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 1
    assert "encoding.H264Crf: Jellyfin has 23, declared 20" in r.output
    assert not post.called
