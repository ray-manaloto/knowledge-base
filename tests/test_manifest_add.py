"""kb_setup.manifest — name derivation + the add() write-guard.

Network-free: name_from_url is pure, and add()'s exists-guard fires BEFORE the
`git ls-remote` in latest_commit, so the refuse-to-clobber path needs no network.
"""

import pytest
from kb_setup import manifest


def test_name_from_url_strips_git_and_trailing_slash() -> None:
    assert manifest.name_from_url("https://github.com/openai/symphony") == "symphony"
    assert manifest.name_from_url("https://github.com/openai/symphony.git") == "symphony"
    assert manifest.name_from_url("https://github.com/openai/symphony/") == "symphony"


def test_add_refuses_to_clobber_existing_manifest(tmp_path) -> None:
    sources = tmp_path / "sources"
    sources.mkdir()
    existing = sources / "symphony.manifest"
    existing.write_text("url = x\nref = main\ncommit = deadbeef\n")
    # exists-guard raises before any network call
    with pytest.raises(FileExistsError):
        manifest.add(sources, manifest.NewSource("https://github.com/openai/symphony"))
    assert "deadbeef" in existing.read_text()
