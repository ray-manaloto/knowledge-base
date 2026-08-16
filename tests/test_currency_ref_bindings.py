# Copyright (c) 2026 Raymond Manaloto
"""kb_setup.currency — the two checks that ask whether the repo agrees with itself.

`_check_ref_bindings` and `_check_skill_stamp` cover the gap measured on
2026-08-15: `kb-currency-check` reported NO graphify manifest drift — correctly,
because the manifest matched the pin — while `graphify_baseline`, the committed
disposition catalog and the installed skill stamp all still named v0.9.42, two
releases behind. Every existing check was green over a real, two-release split.

Both directions for every case, and one case the engine specifically must NOT
render green: a binding whose pattern matches nothing. A renamed anchor turns a
declared check into a silent no-op, which is the exact shape
`probes-need-a-control-arm.md` exists to catch, so it is DRIFT here.
"""

import pytest
from kb_setup.currency import config, sync

_CONSTANT = '_ACCEPTED_GRAPHIFY_REF = "([^"]+)"'


def _repo(tmp_path, *, bindings: str = "", skill_stamp: str = "") -> config.ToolSpec:
    (tmp_path / "mise.toml").write_text(
        '[tools]\n"pipx:graphifyy" = { version = "0.9.44" }\n', encoding="utf-8"
    )
    (tmp_path / "currency.toml").write_text(
        "[tool.graphify]\n"
        'mise_key = "pipx:graphifyy"\n'
        'binary = "graphify"\n'
        'manifest = "sources/graphify.manifest"\n'
        f"{skill_stamp}"
        f"{bindings}",
        encoding="utf-8",
    )
    return config.load(tmp_path)[0]


def _manifest(root, *, ref: str = "v0.9.44", commit: str = "a" * 40) -> None:
    path = root / "sources" / "graphify.manifest"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"url = https://example/x\nref = {ref}\ncommit = {commit}\n", encoding="utf-8")


def _binding(path: str, pattern: str, field: str = "ref") -> str:
    return (
        "\n[[tool.graphify.ref_binding]]\n"
        f"path = {path!r}\n"
        f"pattern = '{pattern}'\n"
        f"field = {field!r}\n"
    )


# --------------------------------------------------------------------------
# _check_ref_bindings
# --------------------------------------------------------------------------


def test_binding_agreeing_with_the_manifest_is_ok(tmp_path):
    spec = _repo(tmp_path, bindings=_binding("code.py", _CONSTANT))
    _manifest(tmp_path)
    (tmp_path / "code.py").write_text('_ACCEPTED_GRAPHIFY_REF = "v0.9.44"\n', encoding="utf-8")

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.OK
    assert "1 revision bindings agree" in finding.detail


def test_binding_naming_an_older_release_is_drift(tmp_path):
    """The live 2026-08-15 defect, reduced: manifest v0.9.44, constant v0.9.42."""
    spec = _repo(tmp_path, bindings=_binding("code.py", _CONSTANT))
    _manifest(tmp_path)
    (tmp_path / "code.py").write_text('_ACCEPTED_GRAPHIFY_REF = "v0.9.42"\n', encoding="utf-8")

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.DRIFT
    assert "reads v0.9.42" in finding.detail
    assert "pins v0.9.44" in finding.detail


def test_commit_binding_is_checked_independently_of_the_ref(tmp_path):
    """A correct tag beside the PREVIOUS release's commit is still drift.

    The two manifest fields are independent — which is why
    `_check_manifest_commit` exists — and a code constant can split the same way.
    """
    spec = _repo(
        tmp_path,
        bindings=(
            _binding("code.py", _CONSTANT)
            + _binding("code.py", 'source_commit="([0-9a-f]{40})"', field="commit")
        ),
    )
    _manifest(tmp_path, ref="v0.9.44", commit="a" * 40)
    (tmp_path / "code.py").write_text(
        f'_ACCEPTED_GRAPHIFY_REF = "v0.9.44"\nsource_commit="{"b" * 40}"\n', encoding="utf-8"
    )

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.DRIFT
    assert "(commit)" in finding.detail
    # The ref half agreed, so it must NOT be reported — a check that flags a
    # correct row alongside a wrong one teaches the reader to skim past both.
    assert "(ref)" not in finding.detail


def test_a_pattern_that_matches_nothing_is_drift_not_a_pass(tmp_path):
    """A renamed anchor is a check that stopped checking — never render it green."""
    spec = _repo(tmp_path, bindings=_binding("code.py", _CONSTANT))
    _manifest(tmp_path)
    (tmp_path / "code.py").write_text('_RENAMED_ACCEPTED_REF = "v0.9.44"\n', encoding="utf-8")

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.DRIFT
    assert "checked NOTHING" in finding.detail


def test_a_missing_bound_file_is_drift(tmp_path):
    spec = _repo(tmp_path, bindings=_binding("gone.py", _CONSTANT))
    _manifest(tmp_path)

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.DRIFT
    assert "file is missing" in finding.detail


def test_no_declared_bindings_is_skip(tmp_path):
    spec = _repo(tmp_path)
    _manifest(tmp_path)

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.SKIP


def test_an_unreadable_manifest_field_does_not_pass(tmp_path):
    """No `commit =` line means the comparison never happened — not that it passed."""
    spec = _repo(tmp_path, bindings=_binding("code.py", "x = ([0-9a-f]{40})", field="commit"))
    path = tmp_path / "sources" / "graphify.manifest"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("url = https://example/x\nref = v0.9.44\n", encoding="utf-8")
    (tmp_path / "code.py").write_text(f"x = {'a' * 40}\n", encoding="utf-8")

    finding = sync._check_ref_bindings(tmp_path, spec)

    assert finding.status == sync.DRIFT
    assert "no readable `commit =`" in finding.detail


# --------------------------------------------------------------------------
# config parsing — a malformed binding must fail loudly, never be dropped
# --------------------------------------------------------------------------


def test_a_pattern_with_no_capture_group_is_refused(tmp_path):
    with pytest.raises(ValueError, match="exactly one capture group"):
        _repo(tmp_path, bindings=_binding("code.py", "_ACCEPTED_GRAPHIFY_REF"))


def test_a_pattern_with_two_capture_groups_is_refused(tmp_path):
    with pytest.raises(ValueError, match="exactly one capture group"):
        _repo(tmp_path, bindings=_binding("code.py", "(a)_REF = (b)"))


def test_an_unknown_field_is_refused(tmp_path):
    with pytest.raises(ValueError, match="field must be one of"):
        _repo(tmp_path, bindings=_binding("code.py", _CONSTANT, field="tree"))


def test_a_binding_without_a_pattern_is_refused(tmp_path):
    with pytest.raises(ValueError, match="needs both 'path' and 'pattern'"):
        _repo(tmp_path, bindings="\n[[tool.graphify.ref_binding]]\npath = 'code.py'\n")


# --------------------------------------------------------------------------
# _check_skill_stamp
# --------------------------------------------------------------------------

_STAMP = 'skill_dir = ".claude/skills/graphify"\nskill_stamp = ".claude/skills/graphify/.v"\n'


def _install_skill(tmp_path, version: str | None) -> None:
    skill = tmp_path / ".claude" / "skills" / "graphify"
    skill.mkdir(parents=True, exist_ok=True)
    if version is not None:
        (skill / ".v").write_text(f"{version}\n", encoding="utf-8")


def test_skill_stamp_matching_the_pin_is_ok(tmp_path):
    spec = _repo(tmp_path, skill_stamp=_STAMP)
    _install_skill(tmp_path, "0.9.44")

    assert sync._check_skill_stamp(tmp_path, spec, "0.9.44").status == sync.OK


def test_skill_stamp_behind_the_pin_is_drift(tmp_path):
    """The live case: stamp 0.9.42, pin 0.9.43, and nothing reported it (#315)."""
    spec = _repo(tmp_path, skill_stamp=_STAMP)
    _install_skill(tmp_path, "0.9.42")

    finding = sync._check_skill_stamp(tmp_path, spec, "0.9.43")

    assert finding.status == sync.DRIFT
    assert "generated by 0.9.42" in finding.detail
    assert "kb-skill-refresh" in finding.detail


def test_an_installed_skill_with_no_stamp_is_drift_not_skip(tmp_path):
    """Installed but unstamped means the version is UNKNOWN, and unknown is not green."""
    spec = _repo(tmp_path, skill_stamp=_STAMP)
    _install_skill(tmp_path, None)

    finding = sync._check_skill_stamp(tmp_path, spec, "0.9.44")

    assert finding.status == sync.DRIFT
    assert "UNKNOWN" in finding.detail


def test_an_empty_stamp_is_drift(tmp_path):
    spec = _repo(tmp_path, skill_stamp=_STAMP)
    _install_skill(tmp_path, "")

    assert sync._check_skill_stamp(tmp_path, spec, "0.9.44").status == sync.DRIFT


def test_an_uninstalled_skill_is_skip(tmp_path):
    """Nothing installed cannot be stale — that is SKIP, and it is honest."""
    spec = _repo(tmp_path, skill_stamp=_STAMP)

    assert sync._check_skill_stamp(tmp_path, spec, "0.9.44").status == sync.SKIP


def test_no_declared_skill_stamp_is_skip(tmp_path):
    spec = _repo(tmp_path)

    assert sync._check_skill_stamp(tmp_path, spec, "0.9.44").status == sync.SKIP


# --------------------------------------------------------------------------
# THIS repo's real config — the bindings must actually reach the files they name
# --------------------------------------------------------------------------


def test_this_repos_bindings_all_resolve_to_a_real_anchor():
    """Every declared binding must MATCH something in the file it names.

    A config row is not a check until its pattern reaches its anchor. Without
    this, a refactor that renames `_ACCEPTED_GRAPHIFY_REF` leaves five cheerful
    rows measuring nothing — and `_check_ref_bindings` would report that as DRIFT
    only when someone happened to run it. Assert it in the suite instead.
    """
    import re
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    spec = next(s for s in config.load(repo_root) if s.name == "graphify")

    assert spec.ref_bindings, "graphify must declare its revision bindings"
    for binding in spec.ref_bindings:
        path = repo_root / binding.path
        assert path.exists(), f"{binding.label}: bound file does not exist"
        found = re.search(binding.pattern, path.read_text(encoding="utf-8"))
        assert found is not None, f"{binding.label}: pattern reaches no anchor"
