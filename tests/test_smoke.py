"""Smoke tests — the scaffold imports and the CLI runs."""

from kb_setup import __version__
from kb_setup.cli import main


def test_version_is_set() -> None:
    assert __version__


def test_cli_version(capsys) -> None:
    rc = main(["--version"])
    assert rc == 0
    assert "kb-setup" in capsys.readouterr().out
