"""The command against a mocked Jellyfin and a stub secretspec."""

import json
import subprocess
import sys

import httpx
import pytest
import respx
from typer.testing import CliRunner

from jellyfin_settings import config
from jellyfin_settings.cli import app

URL = "http://jellyfin.test"
STATE = {
    "/System/Configuration/encoding": {"H264Crf": 23},
    "/Users": [{"Name": "u", "Id": "42", "Configuration": {"SubtitleMode": "Default"}}],
    "/Library/VirtualFolders": [],
}


@pytest.fixture
def files(script, tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"url": URL, "encoding": {"H264Crf": 20}}))
    return settings, script("secretspec", "echo test-key"), tmp_path / "stamp"


def mock_jellyfin(mock, encoding_status=204):
    """Routes for Jellyfin's state; returns the encoding and user configuration POST routes."""
    mock.get(f"{URL}/System/Info/Public").respond(200, json={})
    for path, body in STATE.items():
        mock.get(f"{URL}{path}").respond(200, json=body)
    return (
        mock.post(f"{URL}/System/Configuration/encoding").respond(encoding_status),
        mock.post(f"{URL}/Users/42/Configuration").respond(204),
    )


def run(*args):
    return CliRunner().invoke(app, list(map(str, args)))


def test_apply_posts_with_the_key_and_writes_the_stamp(files):
    settings, stub, stamp = files
    with respx.mock as mock:
        post, _ = mock_jellyfin(mock)
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert r.exit_code == 0, r.output
    assert post.calls.last.request.headers["Authorization"] == 'MediaBrowser Token="test-key"'
    assert json.loads(post.calls.last.request.content) == {"H264Crf": 20}
    assert stamp.read_text().strip()


def test_apply_with_matching_stamp_contacts_nothing(files):
    settings, stub, stamp = files
    with respx.mock as mock:
        mock_jellyfin(mock)
        first = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert first.exit_code == 0, first.output
    assert stamp.exists()
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


def test_apply_without_the_key_exits_0_sends_nothing_and_writes_no_stamp(files, script):
    settings, _, stamp = files
    failing = script("failing-secretspec", "exit 1")
    with respx.mock(assert_all_called=False) as mock:
        post, _ = mock_jellyfin(mock)
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", failing)
    assert r.exit_code == 0
    assert "couldn't read JELLYFIN_API_KEY" in r.output
    assert not post.called
    assert not stamp.exists()


def test_apply_dry_run_prints_requests_sends_nothing_and_writes_no_stamp(files):
    settings, stub, stamp = files
    with respx.mock(assert_all_called=False) as mock:
        post, _ = mock_jellyfin(mock)
        r = run("apply", settings, "--dry-run", "--if-changed", stamp, "--secretspec", stub)
    assert r.exit_code == 0, r.output
    assert "would POST /System/Configuration/encoding" in r.output
    assert not post.called
    assert not stamp.exists()


def test_apply_stops_at_the_first_refused_request_and_writes_no_stamp(files):
    settings, stub, stamp = files
    settings.write_text(
        json.dumps({"url": URL, "encoding": {"H264Crf": 20}, "users": {"u": {"SubtitleMode": "Always"}}})
    )
    with respx.mock(assert_all_called=False) as mock:
        encoding, user = mock_jellyfin(mock, encoding_status=500)
        r = run("apply", settings, "--if-changed", stamp, "--secretspec", stub)
    assert r.exit_code == 0
    assert "Jellyfin refused a request" in r.output
    assert (encoding.called, user.called) == (True, False)
    assert not stamp.exists()


def test_diff_reports_drift_with_exit_1_and_sends_nothing(files):
    settings, stub, _ = files
    with respx.mock(assert_all_called=False) as mock:
        post, _ = mock_jellyfin(mock)
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 1
    assert "encoding.H264Crf: Jellyfin has 23, declared 20" in r.output
    assert not post.called


def test_diff_without_drift_exits_0(files):
    settings, stub, _ = files
    settings.write_text(json.dumps({"url": URL, "encoding": {"H264Crf": 23}}))
    with respx.mock(assert_all_called=False) as mock:
        mock_jellyfin(mock)
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 0, r.output
    assert "Jellyfin matches the declared settings" in r.output


def test_diff_reports_a_skipped_user_as_drift(files):
    settings, stub, _ = files
    settings.write_text(json.dumps({"url": URL, "users": {"nobody": {"X": 1}}}))
    with respx.mock(assert_all_called=False) as mock:
        mock_jellyfin(mock)
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 1
    assert "users.nobody: no such Jellyfin user; skipped" in r.output


def test_diff_without_jellyfin_exits_2(files):
    settings, stub, _ = files
    with respx.mock as mock:
        mock.get(f"{URL}/System/Info/Public").mock(side_effect=httpx.ConnectError("down"))
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 2
    assert "doesn't answer" in r.output


def test_diff_without_the_key_exits_2(files, script):
    settings, _, _ = files
    with respx.mock(assert_all_called=False) as mock:
        mock_jellyfin(mock)
        r = run("diff", settings, "--secretspec", script("failing-secretspec", "exit 1"))
    assert r.exit_code == 2
    assert "couldn't read JELLYFIN_API_KEY" in r.output


def test_empty_settings_reach_jellyfin_at_the_default_url(files):
    settings, stub, _ = files
    settings.write_text("{}")
    with respx.mock(assert_all_called=False) as mock:
        public = mock.get("http://localhost:8096/System/Info/Public").respond(503)
        r = run("diff", settings, "--secretspec", stub)
    assert r.exit_code == 2
    assert public.called
    assert "doesn't answer at http://localhost:8096" in r.output


@pytest.mark.parametrize("command", ["apply", "diff"])
def test_an_unknown_key_exits_2_and_contacts_nothing(files, command):
    settings, stub, _ = files
    settings.write_text(json.dumps({"url": URL, "encodng": {"H264Crf": 20}}))
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route()
        r = run(command, settings, "--secretspec", stub)
    assert r.exit_code == 2
    assert "bad settings: unknown key 'encodng'" in r.output
    assert not route.called


def test_config_show_defaults_prints_the_shipped_file():
    r = run("config", "show", "--defaults")
    assert r.exit_code == 0, r.output
    assert r.output == config.defaults_text()


def test_config_show_prints_the_settings_merged_over_the_defaults(files):
    settings, _, _ = files
    r = run("config", "show", settings)
    assert r.exit_code == 0, r.output
    assert json.loads(r.output) == {**config.defaults(), "url": URL, "encoding": {"H264Crf": 20}}


def test_module_runs_as_the_command():
    result = subprocess.run(
        [sys.executable, "-m", "jellyfin_settings", "--help"], capture_output=True, text=True, check=True
    )
    assert "Usage: jellyfin-settings" in result.stdout
    assert all(command in result.stdout for command in ("apply", "diff", "config"))
