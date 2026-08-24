# Copyright (c) 2026 Raymond Manaloto
"""`graphify_native_extract` — mostly dry-run only; no test makes a provider call.

Every check builds its own `tmp_path` tree standing in for the repo root, so
nothing reads or writes the real `sources/graphify` clone or `graphify-out/`.

The `--artifacts` real-dispatch tests below are the one exception to
"dry-run only": they call `_run_artifacts`/`native_extract_main` for real, with
`kb_setup.artifacts.generate` replaced by a spy and `assert_pinned_graphify`
stubbed out, so nothing here ever shells out to graphify or a provider — see
the module's own "Verification scope" docstring section for why this one path
earns a real-dispatch test where extract/cluster do not.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup import artifacts
from kb_setup import graphify_native_extract as gne
from kb_setup.result import Rc

if TYPE_CHECKING:
    import pytest


def _make_target(repo_root: Path) -> Path:
    target = repo_root / gne.DEFAULT_TARGET
    target.mkdir(parents=True)
    return target


# --- argv shape ---------------------------------------------------------------


def test_resolve_argv_carries_mode_deep_and_backend_claude_cli(tmp_path: Path) -> None:
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    argv = gne.resolve_argv("/repo/.venv/bin/graphify", opts)

    assert argv[0] == "/repo/.venv/bin/graphify"
    assert argv[1] == "extract"
    assert "--mode" in argv
    assert argv[argv.index("--mode") + 1] == "deep"
    assert "--backend" in argv
    assert argv[argv.index("--backend") + 1] == "claude-cli"
    # Reverted, this must fail: --out must reach graphify's own argv, or a
    # caller's directory choice is silently ignored and extraction lands
    # wherever graphify defaults to (the target itself — the exact hazard
    # `_refuse_out` exists to keep this module from causing).
    assert "--out" in argv
    assert argv[argv.index("--out") + 1] == str(opts.out)


def test_resolve_argv_omits_optional_flags_when_unset(tmp_path: Path) -> None:
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    argv = gne.resolve_argv("graphify", opts)
    assert "--token-budget" not in argv
    assert "--max-concurrency" not in argv


def test_resolve_argv_carries_token_budget_and_max_concurrency_when_set(tmp_path: Path) -> None:
    opts = gne.Options(
        target=tmp_path / "sources/graphify",
        out=tmp_path / "out",
        token_budget=12345,
        max_concurrency=2,
    )
    argv = gne.resolve_argv("graphify", opts)
    assert argv[argv.index("--token-budget") + 1] == "12345"
    assert argv[argv.index("--max-concurrency") + 1] == "2"


# --- environment ---------------------------------------------------------------


def test_resolve_env_carries_model_and_is_built_from_clean_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Arm both directions.

    The trigger must be PRESENT in os.environ first
    (`probes-need-a-control-arm.md`), or this passes on any host where it was
    never set — a check that can only pass.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-should-never-reach-a-subprocess")
    assert "GEMINI_API_KEY" in os.environ  # arm: the fixture really set it

    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    env = gne.resolve_env(opts)

    assert env[gne._MODEL_ENV] == gne.DEFAULT_MODEL
    # Checked against the KEY SET, never `"X" not in env` on the dict itself: a
    # failing membership assert on a dict reprs the whole thing in the pytest
    # diff, which would print every inherited env VALUE (this process's real
    # secrets included) to the test output. A frozenset of the keys reprs as
    # names only.
    keys = frozenset(env)
    assert "GEMINI_API_KEY" not in keys  # clean_env()'s strip reached this env too


def test_resolve_env_omits_parallel_override_by_default(tmp_path: Path) -> None:
    """The dissent: no silent parallel opt-in. Reverted, this must fail.

    Checked against a frozenset of keys computed on its OWN line, not inlined
    in the assert: pytest's assertion rewriter reprs every sub-expression it
    can reach, and `assert X not in frozenset(env)` still shows `env`'s own
    repr while explaining the `frozenset(env)` call — precomputing `keys`
    keeps `env` (this process's real secrets) out of the assert expression
    entirely. See `test_resolve_env_carries_model_and_is_built_from_clean_env`.
    """
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    env = gne.resolve_env(opts)
    keys = frozenset(env)
    assert gne._PARALLEL_ENV not in keys


def test_resolve_env_sets_parallel_override_only_when_explicitly_allowed(tmp_path: Path) -> None:
    opts = gne.Options(
        target=tmp_path / "sources/graphify",
        out=tmp_path / "out",
        allow_parallel_claude_cli=True,
    )
    env = gne.resolve_env(opts)
    assert env[gne._PARALLEL_ENV] == "1"


def test_custom_model_flows_through_to_the_environment(tmp_path: Path) -> None:
    opts = gne.Options(
        target=tmp_path / "sources/graphify", out=tmp_path / "out", model="claude-sonnet-5"
    )
    env = gne.resolve_env(opts)
    assert env[gne._MODEL_ENV] == "claude-sonnet-5"


# --- refusals --------------------------------------------------------------


def test_out_at_repo_root_is_refused(tmp_path: Path) -> None:
    """Reverted (out == repo_root allowed), this must fail.

    It is the exact shape that would clobber the aggregate
    graphify-out/graph.json.
    """
    _make_target(tmp_path)
    opts = gne.Options(target=tmp_path / gne.DEFAULT_TARGET, out=tmp_path)
    assert gne._refuse_out(tmp_path, opts) is not None


def test_out_inside_the_pinned_clone_is_refused(tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    opts = gne.Options(target=target, out=target / "graphify-out")
    assert gne._refuse_out(tmp_path, opts) is not None


def test_out_outside_repo_root_and_clone_is_not_refused(tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    opts = gne.Options(target=target, out=tmp_path / gne.DEFAULT_OUT)
    assert gne._refuse_out(tmp_path, opts) is None


def test_missing_target_is_refused(tmp_path: Path) -> None:
    """The pinned clone is gitignored and may be absent on a fresh checkout.

    This must refuse, never silently succeed or crash.
    """
    opts = gne.Options(target=tmp_path / gne.DEFAULT_TARGET, out=tmp_path / gne.DEFAULT_OUT)
    assert gne._refuse_target(opts) is not None


def test_existing_target_is_not_refused(tmp_path: Path) -> None:
    target = _make_target(tmp_path)
    opts = gne.Options(target=target, out=tmp_path / gne.DEFAULT_OUT)
    assert gne._refuse_target(opts) is None


# --- the CLI boundary: native_extract_main ----------------------------------


def test_main_refuses_missing_target_with_not_run(tmp_path: Path) -> None:
    rc = gne.native_extract_main(tmp_path, [])
    assert rc == Rc.NOT_RUN


def test_main_refuses_repo_root_out_with_bad_request(tmp_path: Path) -> None:
    _make_target(tmp_path)
    rc = gne.native_extract_main(tmp_path, ["--out", "."])
    assert rc == Rc.BAD_REQUEST


def test_main_refuses_unrecognised_flag_with_bad_request(tmp_path: Path) -> None:
    _make_target(tmp_path)
    rc = gne.native_extract_main(tmp_path, ["--not-a-real-flag"])
    assert rc == Rc.BAD_REQUEST


def test_dry_run_exits_ok_without_invoking_graphify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The core promise: --dry-run never invokes graphify.

    Assert it by making any subprocess call blow up — reverted (dry-run falls
    through to `_run_real`), this must fail instead of passing quietly.
    """
    _make_target(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("graphify must not be invoked under --dry-run")

    monkeypatch.setattr(gne.subprocess, "run", _boom)

    rc = gne.native_extract_main(tmp_path, ["--dry-run"])
    assert rc == Rc.OK


def test_dry_run_output_never_prints_the_full_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The secret-exposure arm.

    A credential-shaped var inherited from the calling shell must not appear
    in the dry-run's stdout, even though `clean_env()` (correctly) keeps it
    for the real subprocess. Reverted to printing the raw `resolve_env()`
    dict, this must fail.
    """
    _make_target(tmp_path)
    monkeypatch.setenv("TOTALLY_NOT_A_REAL_CREDENTIAL_SENTINEL", "should-never-be-printed")

    rc = gne.native_extract_main(tmp_path, ["--dry-run"])
    assert rc == Rc.OK

    out = capsys.readouterr().out
    assert "should-never-be-printed" not in out
    assert "TOTALLY_NOT_A_REAL_CREDENTIAL_SENTINEL" not in out
    # The overlay itself IS printed — the dry-run must still be useful.
    assert gne.DEFAULT_MODEL in out
    assert "extract" in out


def test_dry_run_missing_target_still_refuses(tmp_path: Path) -> None:
    """A dry run previews a plan.

    A plan for a target that cannot exist is not a valid preview either.
    Reverted (dry-run skips the target check), this must fail.
    """
    rc = gne.native_extract_main(tmp_path, ["--dry-run"])
    assert rc == Rc.NOT_RUN


# --- --cluster ---------------------------------------------------------------


def _make_extracted_out(repo_root: Path) -> Path:
    """A `--out` tree that already looks extracted: `graphify-out/graph.json`."""
    out = repo_root / gne.DEFAULT_OUT
    graph_json = out / "graphify-out" / "graph.json"
    graph_json.parent.mkdir(parents=True)
    graph_json.write_text("{}")
    return out


def test_resolve_cluster_argv_targets_the_out_directory_not_its_graphify_out(
    tmp_path: Path,
) -> None:
    """`cluster-only <path>` takes the SAME shape `extract --out` wrote to.

    Reverted to passing `opts.out / "graphify-out"`, this must fail —
    graphify's own default `--graph` is already `<path>/graphify-out/graph.json`.
    """
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    argv = gne.resolve_cluster_argv("/repo/.venv/bin/graphify", opts)
    assert argv == ["/repo/.venv/bin/graphify", "cluster-only", str(opts.out)]


def test_resolve_cluster_env_is_built_from_clean_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same subprocess-environment discipline as the extract path.

    Armed: the trigger must be PRESENT first, or this passes on any host
    where it was never set.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "sentinel-should-never-reach-a-subprocess")
    assert "GEMINI_API_KEY" in os.environ

    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    env = gne.resolve_cluster_env(opts)
    keys = frozenset(env)
    assert "GEMINI_API_KEY" not in keys


def test_resolve_cluster_env_carries_no_backend_selecting_vars(tmp_path: Path) -> None:
    """No `GRAPHIFY_CLAUDE_CLI_MODEL`/`_PARALLEL` in the cluster environment.

    cluster-only never gets a `--backend` flag from this module, so those
    vars would be inert AND misleading. Reverted to reusing `env_overlay`,
    this must fail.
    """
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / "out")
    env = gne.resolve_cluster_env(opts)
    keys = frozenset(env)
    assert gne._MODEL_ENV not in keys
    assert gne._PARALLEL_ENV not in keys


def test_cluster_refuses_when_no_graph_json_exists(tmp_path: Path) -> None:
    opts = gne.Options(target=tmp_path / "sources/graphify", out=tmp_path / gne.DEFAULT_OUT)
    assert gne._refuse_cluster_input(opts) is not None


def test_cluster_is_not_refused_when_graph_json_exists(tmp_path: Path) -> None:
    out = _make_extracted_out(tmp_path)
    opts = gne.Options(target=tmp_path / "sources/graphify", out=out)
    assert gne._refuse_cluster_input(opts) is None


def test_main_cluster_refuses_missing_graph_json_with_not_run(tmp_path: Path) -> None:
    rc = gne.native_extract_main(tmp_path, ["--cluster"])
    assert rc == Rc.NOT_RUN


def test_main_cluster_never_requires_the_pinned_clone_target(tmp_path: Path) -> None:
    """--cluster is standalone: it must not check `opts.target` at all.

    No `sources/graphify` is created here — only the already-extracted `--out`
    tree — and the dry run must still succeed. Reverted to routing --cluster
    through `_refuse_target`, this must fail.
    """
    _make_extracted_out(tmp_path)
    rc = gne.native_extract_main(tmp_path, ["--cluster", "--dry-run"])
    assert rc == Rc.OK


def test_cluster_dry_run_exits_ok_without_invoking_graphify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_extracted_out(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("graphify must not be invoked under --cluster --dry-run")

    monkeypatch.setattr(gne.subprocess, "run", _boom)

    rc = gne.native_extract_main(tmp_path, ["--cluster", "--dry-run"])
    assert rc == Rc.OK


def test_cluster_dry_run_output_names_cluster_only_and_the_out_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = _make_extracted_out(tmp_path)
    opts = gne.Options(target=tmp_path / "sources/graphify", out=out)
    gne._print_cluster_dry_run("graphify", opts)
    printed = capsys.readouterr().out
    assert "cluster-only" in printed
    assert str(out) in printed


# --- --artifacts --------------------------------------------------------------


def test_artifacts_flag_with_no_names_means_all(tmp_path: Path) -> None:
    opts = gne._parse(tmp_path, ["--artifacts"])
    assert opts.artifacts is True
    assert opts.artifacts_views == ()


def test_artifacts_flag_consumes_view_names_until_the_next_flag(tmp_path: Path) -> None:
    """Reverted (view consumption stops early or swallows --dry-run), this must fail."""
    opts = gne._parse(tmp_path, ["--artifacts", "wiki", "graphml", "--dry-run"])
    assert opts.artifacts_views == ("wiki", "graphml")
    assert opts.dry_run is True


def test_cluster_and_artifacts_together_is_rejected(tmp_path: Path) -> None:
    rc = gne.native_extract_main(tmp_path, ["--cluster", "--artifacts"])
    assert rc == Rc.BAD_REQUEST


def test_main_artifacts_refuses_missing_graph_json_with_not_run(tmp_path: Path) -> None:
    rc = gne.native_extract_main(tmp_path, ["--artifacts"])
    assert rc == Rc.NOT_RUN


def test_main_artifacts_never_requires_the_pinned_clone_target(tmp_path: Path) -> None:
    """--artifacts is standalone, same as --cluster: no `sources/graphify` here.

    Reverted to routing --artifacts through `_refuse_target`, this must fail.
    """
    _make_extracted_out(tmp_path)
    rc = gne.native_extract_main(tmp_path, ["--artifacts", "--dry-run"])
    assert rc == Rc.OK


def test_artifacts_dry_run_exits_ok_without_invoking_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_extracted_out(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("artifacts.generate must not run under --artifacts --dry-run")

    monkeypatch.setattr(artifacts, "generate", _boom)

    rc = gne.native_extract_main(tmp_path, ["--artifacts", "--dry-run"])
    assert rc == Rc.OK


def test_artifacts_dry_run_output_names_both_roots_distinctly(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The dry-run preview must show which value plays which role.

    Reverted to printing only `opts.out` (or only `repo_root`), this must
    fail: showing just one root is not a preview of what `_run_artifacts`
    actually does with two DIFFERENT roots (`repo_root` anchors the exe/venv,
    `opts.out` is `generate`'s `graph_root`) — a dry run that hides the split
    this whole capability exists for is not a useful preview of it.
    """
    fake_repo_root = tmp_path / "real-repo-root"
    out = tmp_path / "scoped-out"
    opts = gne.Options(target=tmp_path / "sources/graphify", out=out, artifacts=True)

    gne._print_artifacts_dry_run(fake_repo_root, opts)
    printed = capsys.readouterr().out

    assert str(out) in printed
    assert str(fake_repo_root) in printed


def test_run_artifacts_resolves_exe_against_repo_root_and_graph_against_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point of `graph_root`.

    Reverted to passing `opts.out` as `generate`'s `repo_root` (or `repo_root`
    as its `graph_root`), this must fail — `graphify_exe`/`ensure_runtime_deps`
    have no fallback and would resolve a `.venv/` that only exists at the real
    project root.
    """
    out = _make_extracted_out(tmp_path)
    calls: list[tuple[Path, list[str] | None, Path | None]] = []

    def fake_generate(repo_root: Path, only: list[str] | None = None, *, graph_root=None) -> int:
        calls.append((repo_root, only, graph_root))
        return 0

    monkeypatch.setattr(gne, "assert_pinned_graphify", lambda _r: None)
    monkeypatch.setattr(artifacts, "generate", fake_generate)

    opts = gne.Options(target=tmp_path / "sources/graphify", out=out, artifacts=True)
    rc = gne._run_artifacts(tmp_path, opts)

    assert rc == 0
    assert calls == [(tmp_path, None, out)]


def test_named_view_filter_flows_through_to_generate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _make_extracted_out(tmp_path)
    calls: list[list[str] | None] = []

    def fake_generate(repo_root: Path, only: list[str] | None = None, *, graph_root=None) -> int:
        calls.append(only)
        return 0

    monkeypatch.setattr(gne, "assert_pinned_graphify", lambda _r: None)
    monkeypatch.setattr(artifacts, "generate", fake_generate)

    opts = gne.Options(
        target=tmp_path / "sources/graphify",
        out=out,
        artifacts=True,
        artifacts_views=("wiki", "graphml"),
    )
    assert gne._run_artifacts(tmp_path, opts) == 0
    assert calls == [["wiki", "graphml"]]


def test_artifacts_dry_run_missing_graph_json_still_refuses(tmp_path: Path) -> None:
    rc = gne.native_extract_main(tmp_path, ["--artifacts", "--dry-run"])
    assert rc == Rc.NOT_RUN


# --- unknown view names: the "0 artifacts = clean rc=0" trap ------------------


def test_no_views_requested_is_never_refused() -> None:
    assert gne._refuse_unknown_views(()) is None


def test_known_view_names_are_not_refused() -> None:
    assert gne._refuse_unknown_views(("wiki", "graphml")) is None


def test_an_unknown_view_name_is_refused_and_named() -> None:
    """Reverted (skip the check), this must fail.

    A typo'd view would otherwise reach `artifacts.generate` as a silent,
    rc=0 no-op.
    """
    problem = gne._refuse_unknown_views(("wiky",))
    assert problem is not None
    assert "wiky" in problem


def test_one_unknown_among_known_views_is_still_refused() -> None:
    """A mix of good and bad names must still refuse.

    The known ones present don't excuse the one that isn't.
    """
    problem = gne._refuse_unknown_views(("wiki", "wiky"))
    assert problem is not None
    assert "wiky" in problem


def test_main_refuses_an_unknown_artifact_view_with_bad_request(tmp_path: Path) -> None:
    """End-to-end.

    Reverted (view names never validated before `--dry-run` prints "all
    good"), this must fail.
    """
    _make_extracted_out(tmp_path)
    rc = gne.native_extract_main(tmp_path, ["--artifacts", "wiky", "--dry-run"])
    assert rc == Rc.BAD_REQUEST
