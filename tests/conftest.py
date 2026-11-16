import stat

import pytest


@pytest.fixture
def script(tmp_path):
    """Writes an executable shell script named name into tmp_path and returns its path."""

    def write(name, body):
        path = tmp_path / name
        path.write_text(f"#!/bin/sh\n{body}\n")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return str(path)

    return write
