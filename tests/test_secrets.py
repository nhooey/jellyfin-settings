"""Reading the key through a stub secretspec."""

import pytest

from jellyfin_settings.secrets import REASON, read_key


def test_key_is_read_with_the_manifest_and_reason(script, tmp_path):
    args = tmp_path / "args"
    stub = script("secretspec", f'printf "%s\\n" "$@" > {args}\necho "  the-key  "')
    assert read_key(stub, "/m.toml") == "the-key"
    assert args.read_text().splitlines() == [
        "--file",
        "/m.toml",
        "get",
        "JELLYFIN_API_KEY",
        "--reason",
        REASON,
    ]


@pytest.mark.parametrize(
    "body",
    [
        pytest.param("echo the-key; exit 1", id="non-zero exit"),
        pytest.param("exit 0", id="no output"),
        pytest.param("echo '   '", id="blank output"),
    ],
)
def test_no_key_when_secretspec_fails(script, body):
    assert read_key(script("secretspec", body), "/m.toml") is None


def test_no_key_when_secretspec_is_missing(tmp_path):
    assert read_key(str(tmp_path / "absent"), "/m.toml") is None


def test_no_key_when_secretspec_times_out(script):
    assert read_key(script("secretspec", "exec sleep 10"), "/m.toml", timeout=0.2) is None
