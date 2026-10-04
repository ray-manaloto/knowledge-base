# Copyright (c) 2026 Raymond Manaloto
"""Real isolated Git inventories arm each offline registry rendering contract."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from kb_setup import models, models_apply


def _repo(root: Path, content: dict[str, str]) -> models_apply.SitesConfig:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    for name, text in content.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    if content:
        subprocess.run(["git", "add", "--", *content], cwd=root, check=True)
    for name, data in models_apply.plugin_bytes().items():
        path = root / ".claude/skills/model-registry" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return models_apply.SitesConfig(
        owned=("owned.md",), exempt=(".claude/skills/model-registry/**",)
    )


def test_registry_definition_is_intrinsically_excluded_but_a_new_pin_site_is_not(tmp_path: Path):
    registry = models.load_registry()
    slug = registry.codex.pins["sol"].slug
    sites = _repo(
        tmp_path,
        {
            "python/src/kb_setup/models.toml": slug,
            "models-sites.toml": slug,
            "owned.md": slug,
        },
    )
    assert models.check_pin_sites(tmp_path, sites, registry) == []
    path = tmp_path / "unowned.md"
    path.write_text(slug)
    subprocess.run(["git", "add", "unowned.md"], cwd=tmp_path, check=True)
    assert any(
        "(d) unowned.md" in line for line in models.check_pin_sites(tmp_path, sites, registry)
    )


def test_stale_owned_pin_changes_render_and_is_reported_separately(tmp_path: Path):
    registry = models.load_registry()
    slug = next(
        slug
        for slug, entry in registry.codex.known.items()
        if entry.family == "sol" and slug != registry.codex.pins["sol"].slug
    )
    sites = _repo(tmp_path, {"owned.md": f"Use `{slug}`.\n"})
    findings = models.check_pin_sites(tmp_path, sites, registry)
    assert any(line.startswith("(a)") for line in findings)
    assert any(line.startswith("(c)") for line in findings)
    models_apply.apply(tmp_path, sites, registry)
    assert models.check_pin_sites(tmp_path, sites, registry) == []


def test_unpinned_family_is_rejected_without_an_invented_replacement(tmp_path: Path):
    registry = models.load_registry()
    slug = next(
        slug
        for slug, entry in registry.codex.known.items()
        if entry.family not in registry.codex.pins
    )
    sites = _repo(tmp_path, {"owned.md": slug})
    assert any(line.startswith("(c)") for line in models.check_pin_sites(tmp_path, sites, registry))


def test_historical_fences_are_exact_and_unbalanced_fences_fail():
    registry = models.load_registry()
    old = next(
        slug
        for slug, entry in registry.codex.known.items()
        if entry.family == "sol" and slug != registry.codex.pins["sol"].slug
    )
    source = f"<!-- models-apply: off -->\n{old}\n<!-- models-apply: on -->\n"
    sites = models_apply.SitesConfig()
    assert models_apply.render("owned.md", source, sites, registry) == source
    assert old not in models_apply.active_text(source)
    with pytest.raises(ValueError, match="unterminated"):
        models_apply.render(
            "owned.md", source.replace("<!-- models-apply: on -->\n", ""), sites, registry
        )


def test_option_c_removes_an_effort_key_and_ignores_untracked_exports(tmp_path: Path):
    registry = models.load_registry()
    name = ".codex/agents/kb-codex-astra-advisor.toml"
    slug = registry.codex.pins["astra"].slug
    _repo(tmp_path, {name: f'model = "{slug}"\nmodel_reasoning_effort = "xhigh"\n'})
    sites = models_apply.SitesConfig(
        owned=(".codex/agents/*.toml",), agent_pairs=(".codex/agents/*.toml",)
    )
    (tmp_path / ".codex/agents/exported-unknown.toml").write_text('model = "invented"\n')
    assert any(line.startswith("(i)") for line in models.check_pin_sites(tmp_path, sites, registry))
    models_apply.apply(tmp_path, sites, registry)
    assert "model_reasoning_effort" not in (tmp_path / name).read_text()
    assert models.check_pin_sites(tmp_path, sites, registry) == []


def test_claude_alias_candidates_skip_descriptions_and_expressions(tmp_path: Path):
    registry = models.load_registry()
    full_id = registry.claude.api["graphify_native_extract"]
    assert isinstance(full_id, str)
    name = ".claude/agents/scratch.md"
    sites = _repo(
        tmp_path,
        {
            name: "---\nmodel: opus\n---\n",
            ".claude/workflows/scratch.js": (
                "model: 'haiku/sonnet/opus per lane'; "
                "model: 'fable, falling back to opus/xhigh'; model: lookup();\n"
            ),
        },
    )
    assert models.check_aliases_only(tmp_path, sites) == []
    (tmp_path / name).write_text(f"---\nmodel: {full_id}\n---\n")
    assert any(line.startswith("(e)") for line in models.check_aliases_only(tmp_path, sites))


def test_strict_command_detection_and_rendering():
    source = (
        "Mention `codex exec`, `codex exec --help` and `codex exec …`.\n"
        "```bash\ncat input | mise exec -- codex exec \\\n  -m fixture -\n```\n"
    )
    rendered = models_apply.render(
        "owned.md", source, models_apply.SitesConfig(), models.load_registry()
    )
    assert "codex exec --strict-config \\" in rendered
    assert "`codex exec`" in rendered
    assert "`codex exec --help`" in rendered
    assert "`codex exec …`" in rendered
    assert not any(
        models_apply._strict_needed(command, inline=inline)
        for command, inline in models_apply._commands(rendered)
    )


def test_unresolved_argv_site_is_a_failure(tmp_path: Path):
    sites = _repo(tmp_path, {"owned.md": "No launch here.\n"})
    sites = models_apply.SitesConfig(
        owned=sites.owned,
        argv_sites=(
            models_apply.ArgvSite("owned.md", flag="--model", value="{codex.pins.sol.slug}"),
        ),
    )
    assert any(
        line.startswith("(b)")
        for line in models.check_pin_sites(tmp_path, sites, models.load_registry())
    )


def test_strict_pipeline_preserves_quoted_mentions_and_help_only_stages():
    source = "```bash\necho 'codex exec -' | codex exec - && codex exec --help\n```\n"
    rendered = models_apply.render(
        "owned.md", source, models_apply.SitesConfig(), models.load_registry()
    )
    assert "echo 'codex exec -'" in rendered
    assert "| codex exec --strict-config -" in rendered
    assert "&& codex exec --help" in rendered


def test_agent_pair_render_does_not_delete_instruction_body_keys():
    source = 'model_reasoning_effort = "high"\ndeveloper_instructions = """\n'
    source += 'model_reasoning_effort = "an-example-value"\n"""\n'
    sites = models_apply.SitesConfig(agent_pairs=(".codex/agents/*.toml",))
    rendered = models_apply.render(
        ".codex/agents/kb-codex-astra-advisor.toml", source, sites, models.load_registry()
    )
    assert not rendered.startswith("model_reasoning_effort")
    assert 'model_reasoning_effort = "an-example-value"' in rendered


def test_plugin_byte_drift_is_reported(tmp_path: Path):
    sites = _repo(tmp_path, {})
    path = tmp_path / ".claude/skills/model-registry/hooks/register.ts"
    path.write_text(path.read_text() + "// scratch byte drift\n")
    assert any(
        line.startswith("(g)")
        for line in models.check_pin_sites(tmp_path, sites, models.load_registry())
    )


def test_d_allowlist_and_fallback_have_independent_failure_arms(tmp_path: Path):
    registry = models.load_registry()
    sites = _repo(
        tmp_path,
        {
            ".codex/config.toml": '[agents]\ndefault_subagent_model = "fixture"\n',
            ".claude/settings.json": "{}\n",
        },
    )
    sites = models_apply.SitesConfig(codex_config=("agents.default_subagent_model",))
    assert models_apply._settings_findings(tmp_path, sites, registry) == []
    path = tmp_path / ".codex/config.toml"
    path.write_text(path.read_text() + '[shell_environment_policy]\ninherit = "core"\n')
    assert any(
        "(k)" in line and "shell_environment_policy.inherit" in line
        for line in models_apply._settings_findings(tmp_path, sites, registry)
    )
    (tmp_path / ".claude/settings.json").write_text('{"fallbackModel": ["opus"]}\n')
    assert any(
        line.startswith("(f)")
        for line in models_apply._settings_findings(tmp_path, sites, registry)
    )


def test_cli_apply_check_never_runs_post_apply(tmp_path: Path):
    _repo(
        tmp_path,
        {"models-sites.toml": '[[post_apply]]\ntask = "a-fresh-task-that-cannot-exist-7b9a"\n'},
    )
    assert models.main(tmp_path, ["apply", "--check", "--sites", "models-sites.toml"]) == 0


def _wrapper_sites_file(tmp_path: Path, extra: str = "") -> Path:
    path = tmp_path / "models-sites.toml"
    path.write_text(
        "[[wrapper_logs]]\n"
        'glob = ".claude/agents/codex-sol-*.md"\n'
        'launch = "codex exec"\n'
        "lane_log = '\"$LOG\"'\n"
        "lane_rc = '\"$LOG.rc\"'\n"
        "rolecheck = '\"$LOG.rolecheck\"'\n"
        'check = "test -s"\n'
        'note = "A custom rolecheck failure is a FAIL."\n' + extra
    )
    return path


def test_wrapper_log_sites_use_consumer_launch_paths_and_check(tmp_path: Path):
    sites = models_apply.load_sites(_wrapper_sites_file(tmp_path))
    source = '```bash\ncodex exec - > "$LOG" 2>&1; echo "$?" > "$LOG.rc"\n```\n'
    registry = models.load_registry()
    name = ".claude/agents/codex-sol-advisor.md"
    rendered = models_apply.render(name, source, sites, registry)
    assert 'test -s "$LOG"; echo "$?" > "$LOG.rolecheck"; exit "$rc"\n' in rendered
    assert 'echo "$rc" > "$LOG.rc"' in rendered
    assert sites.wrapper_logs[0].note in rendered
    assert "$KB_LANE" not in rendered
    assert "codex-log-check" not in rendered
    assert models_apply.render(name, rendered, sites, registry) == rendered
    astra = ".claude/agents/codex-astra-advisor.md"
    unsited = models_apply.render(astra, source, models_apply.SitesConfig(), registry)
    assert models_apply.render(astra, source, sites, registry) == unsited


@pytest.mark.parametrize(
    "name", [".claude/agents/codex-sol-advisor.md", ".claude/agents/kb-codex-advisor.md"]
)
def test_removing_wrapper_log_site_adds_no_check(tmp_path: Path, name: str):
    path = _wrapper_sites_file(tmp_path)
    path.write_text("")
    source = "```bash\nmise run kb-codex -- --write\n```\n"
    sites = models_apply.load_sites(path)
    rendered = models_apply.render(name, source, sites, models.load_registry())
    assert rendered == source
    assert "rolecheck" not in rendered


def test_wrapper_log_site_rejects_unknown_keys(tmp_path: Path):
    path = _wrapper_sites_file(tmp_path, 'unknown = "must fail"\n')
    with pytest.raises(TypeError, match="unknown"):
        models_apply.load_sites(path)
    assert models.main(tmp_path, ["apply", "--check", "--sites", str(path)]) == 1


def _owned_wrapper_sites_file(tmp_path: Path, content: dict[str, str]) -> Path:
    _repo(tmp_path, content)
    path = _wrapper_sites_file(tmp_path)
    path.write_text(
        '[[owned]]\nglob = "owned*.md"\n'
        + path.read_text().replace(".claude/agents/codex-sol-*.md", "owned*.md")
    )
    return path


def _assert_wrapper_load_failure(
    path: Path, field: str, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises((TypeError, ValueError), match=field):
        models_apply.load_sites(path)
    assert models.main(path.parent, ["apply", "--check", "--sites", str(path)]) == 1
    captured = capsys.readouterr()
    assert "(h) models-apply load/check failure:" in captured.out
    assert field in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("lane_rc", [None, 'lane_rc = ""\n'], ids=["unset", "empty"])
def test_f1_wrapper_lane_rc_is_required_and_nonempty(tmp_path: Path, capsys, lane_rc):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": "No launch here.\n"})
    path.write_text(path.read_text().replace("lane_rc = '\"$LOG.rc\"'\n", lane_rc or ""))
    _assert_wrapper_load_failure(path, "lane_rc", capsys)


@pytest.mark.parametrize(
    ("glob", "content", "expected"),
    [
        (
            "other.md",
            {"owned.md": "No launch here.\n", "other.md": "```bash\ncodex exec -\n```\n"},
            "(b) wrapper log glob does not resolve: other.md",
        ),
        (
            "owned*.md",
            {
                "owned.md": (
                    "Mention `codex exec`.\n```python\ncodex exec -\n```\n"
                    "```bash\necho no-launch\n```\n"
                ),
                "owned-control.md": "```bash\ncodex exec --strict-config -\n```\n",
            },
            "(b) owned.md: wrapper launch does not resolve: codex exec",
        ),
    ],
    ids=["owned-miss", "launch-miss"],
)
def test_f2_wrapper_site_requires_owned_files_and_each_fenced_launch(
    tmp_path, glob, content, expected
):
    path = _owned_wrapper_sites_file(tmp_path, content)
    text = path.read_text()
    start = text.index("[[wrapper_logs]]")
    path.write_text(text[:start] + text[start:].replace("owned*.md", glob))
    sites = models_apply.load_sites(path)
    findings = models.check_pin_sites(tmp_path, sites, models.load_registry())
    assert expected in findings
    assert not any("owned-control.md: wrapper launch" in finding for finding in findings)


@pytest.mark.parametrize("field", ["lane_log", "lane_rc", "rolecheck"])
@pytest.mark.parametrize("value", ["'\"\"'", "'\"unclosed'"], ids=["empty-word", "unclosed"])
def test_wrapper_path_fields_must_parse_to_a_path(tmp_path: Path, capsys, field, value):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": "No launch here.\n"})
    text = path.read_text()
    line = next(row for row in text.splitlines() if row.startswith(f"{field} = "))
    path.write_text(text.replace(line, f"{field} = {value}"))
    _assert_wrapper_load_failure(path, field, capsys)


_LAUNCHING = "```bash\ncodex exec --strict-config -\n```\n"


@pytest.mark.parametrize("arm", ["excluded", "control"])
def test_wrapper_exclude_keeps_new_launchers_bound(tmp_path: Path, arm: str):
    """N1: an exclusion, not a narrowed glob, so a NEW launching file stays bound."""
    content = {"owned-lane.md": "You ARE the lane.\n", "owned-new.md": _LAUNCHING}
    path = _owned_wrapper_sites_file(tmp_path, content)
    excluded = arm == "excluded"
    if excluded:
        path.write_text(path.read_text() + 'exclude = ["owned-lane.md"]\n')
    findings = models.check_pin_sites(
        tmp_path, models_apply.load_sites(path), models.load_registry()
    )
    launchless = "(b) owned-lane.md: wrapper launch does not resolve: codex exec"
    assert (launchless in findings) is not excluded
    assert "(a) owned-new.md: differs from models-apply render" in findings


def test_wrapper_exclude_that_matches_nothing_is_reported(tmp_path: Path):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": _LAUNCHING})
    path.write_text(path.read_text() + 'exclude = ["owned-typo.md"]\n')
    findings = models.check_pin_sites(
        tmp_path, models_apply.load_sites(path), models.load_registry()
    )
    assert "(b) wrapper log exclude does not resolve: owned-typo.md" in findings


@pytest.mark.parametrize("value", ['""', '[""]', "[5]"], ids=["str", "empty", "non-str"])
def test_wrapper_exclude_rejects_invalid_values(tmp_path: Path, capsys, value: str):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": _LAUNCHING})
    path.write_text(path.read_text() + f"exclude = {value}\n")
    _assert_wrapper_load_failure(path, "exclude", capsys)


@pytest.mark.parametrize(
    "unknown",
    ["[[wrapper_log]]\n", "[unknown]\nvalue = 1\n", "unknown = 1\n"],
    ids=["misspelt-table", "unknown-table", "unknown-key"],
)
def test_f3_wrapper_site_rejects_unknown_top_level_keys(tmp_path: Path, capsys, unknown):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": "No launch here.\n"})
    if unknown.startswith("[[wrapper_log]]"):
        path.write_text(path.read_text().replace("[[wrapper_logs]]", unknown.strip()))
        field = "wrapper_log"
    else:
        path.write_text(unknown + path.read_text())
        field = "unknown"
    _assert_wrapper_load_failure(path, field, capsys)


@pytest.mark.parametrize("field", ["launch", "check", "lane_log", "rolecheck", "lane_rc"])
@pytest.mark.parametrize("value", ['""', "1"], ids=["empty", "non-str"])
def test_f4_wrapper_site_fields_require_nonempty_strings(tmp_path, capsys, field, value):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": "```bash\ncodex exec -\n```\n"})
    path.write_text(
        re.sub(rf"^{field} = .*", f"{field} = {value}", path.read_text(), flags=re.MULTILINE)
    )
    _assert_wrapper_load_failure(path, field, capsys)


def test_f5_empty_wrapper_lane_log_returns_load_finding_without_traceback(tmp_path: Path, capsys):
    path = _owned_wrapper_sites_file(tmp_path, {"owned.md": "```bash\ncodex exec -\n```\n"})
    path.write_text(path.read_text().replace("lane_log = '\"$LOG\"'", 'lane_log = ""'))
    assert models.main(tmp_path, ["apply", "--check", "--sites", str(path)]) == 1
    captured = capsys.readouterr()
    assert "(h) models-apply load/check failure:" in captured.out
    assert "lane_log" in captured.out
    assert "Traceback" not in captured.err


def test_wrapper_log_site_must_resolve_against_tracked_files(tmp_path: Path):
    _repo(tmp_path, {"owned.md": "No wrapper here.\n"})
    sites = models_apply.load_sites(_wrapper_sites_file(tmp_path))
    assert any(
        "wrapper log glob does not resolve" in finding
        for finding in models.check_pin_sites(tmp_path, sites, models.load_registry())
    )


@pytest.mark.parametrize(
    "suffix",
    [
        " &",
        ' | tee "$LOG"',
        ' > "$LOG" 2>&1; echo "$?" > "$LOG.rc"',
        " > out.txt",
        " 2> errors.txt",
        ' &> "${LOG}"',
        ' >> "${LOG}"',
    ],
)
def test_consumer_wrapper_log_sites_preserve_shell_failure_and_redirects(
    tmp_path: Path, suffix: str
):
    stub = tmp_path / "codex"
    stub.write_text("#!/bin/sh\necho output\necho warning >&2\nexit 7\n")
    stub.chmod(0o755)
    log = tmp_path / "consumer.log"
    log.write_text("retained\n")
    sites = models_apply.load_sites(_wrapper_sites_file(tmp_path))
    source = f"```bash\ncodex exec -{suffix}\n```\n"
    name = ".claude/agents/codex-sol-advisor.md"
    registry = models.load_registry()
    rendered = models_apply.render(name, source, sites, registry)
    assert models_apply.render(name, rendered, sites, registry) == rendered
    block = re.search(r"```bash\n(.*?)```", rendered, re.DOTALL)
    assert block is not None
    result = subprocess.run(
        ["bash", "-c", block[1]],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "LOG": str(log)},
        capture_output=True,
        check=False,
    )
    assert result.returncode == 7, rendered
    assert (tmp_path / "consumer.log.rolecheck").read_text() == "0\n"
    if "out.txt" in suffix:
        assert (tmp_path / "out.txt").read_text() == "output\n"
        assert log.read_text() == "warning\n"
    elif "errors.txt" in suffix:
        assert (tmp_path / "errors.txt").read_text() == "warning\n"
        assert log.read_text() == "output\n"
    if ">>" in suffix:
        assert log.read_text().startswith("retained\noutput\n")
    if "LOG.rc" in suffix:
        assert (tmp_path / "consumer.log.rc").read_text() == "7\n"


def test_both_codex_builders_place_strict_after_the_subcommand():
    from kb_setup import codex_run

    registry = models.load_registry()
    default = registry.codex.dispatch["kb_codex"]
    argv = codex_run._codex_argv(codex_run.LaneSpec())
    assert argv[:3] == ["codex", "exec", "--strict-config"]
    assert argv[argv.index("--model") + 1] == default.slug
    assert f"model_reasoning_effort={default.effort}" in argv
    review = codex_run._review_argv(codex_run.ReviewSpec(base="main"))
    assert review[:3] == ["codex", "review", "--strict-config"]
    assert f'review_model="{default.slug}"' in review


def test_rendered_wrapper_preserves_lane_failure(tmp_path: Path):
    stub = tmp_path / "mise"
    stub.write_text('#!/bin/sh\nif [ "$2" = "kb-codex" ]; then exit 7; fi\nexit 0\n')
    stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "KB_LANE": str(tmp_path)}
    (tmp_path / "prompt.md").write_text("fixture\n")
    (tmp_path / "method.txt").write_text("fixture\n")
    root = Path(__file__).resolve().parents[1]
    blocks = []
    for name in (
        ".claude/agents/kb-codex-advisor.md",
        ".codex/agents/kb-codex-advisor.toml",
        ".claude/agents/kb-codex-astra-advisor.md",
        ".claude/agents/kb-codex-astra-reviewer.md",
        ".codex/agents/kb-codex-astra-reviewer.toml",
    ):
        source = (root / name).read_text()
        sites = models_apply.load_sites(root / "models-sites.toml")
        rendered = models_apply.render(name, source, sites, models.load_registry())
        for block in re.findall(r"```bash\n(.*?)```", rendered, re.DOTALL):
            launch = re.search(r"^(?:cat .*?\| )?mise run kb-codex --", block, re.MULTILINE)
            if launch:
                blocks.append(
                    block[launch.start() :]
                    .replace("<FIXED>", "fixture-ref")
                    .replace("<HEAD SHA>", "fixture-head")
                )
    assert len(blocks) == 7
    for block in blocks:
        result = subprocess.run(["bash", "-c", block], env=env, check=False)
        assert result.returncode == 7, block


def test_strict_site_selection_preserves_prose_docstrings_and_antipatterns():
    source = (
        'Wrong: `codex exec "prompt"` without stdin hangs.\n'
        "Never `codex exec --full-auto`; it does not exist.\n"
        "Use `codex exec resume --last` to resume.\n"
        "`codex exec -`\n"
        "Mention the identical `codex exec -` in prose.\n"
        "```bash\ncat input | codex exec -\n```\n"
    )
    rendered = models_apply.render(
        "owned.md", source, models_apply.SitesConfig(), models.load_registry()
    )
    assert 'Wrong: `codex exec "prompt"` without stdin hangs.' in rendered
    assert "Never `codex exec --full-auto`" in rendered
    assert "Use `codex exec resume --last`" in rendered
    assert "Mention the identical `codex exec -` in prose." in rendered
    assert "`codex exec --strict-config -`\n" in rendered
    assert "| codex exec --strict-config -\n" in rendered
    assert (
        models_apply.render(
            "owned.md", rendered, models_apply.SitesConfig(), models.load_registry()
        )
        == rendered
    )
    python = '"""The `codex exec review` surface and `codex exec --ephemeral`."""\n'
    assert (
        models_apply.render("owned.py", python, models_apply.SitesConfig(), models.load_registry())
        == python
    )


@pytest.mark.parametrize(
    "redirect",
    [
        "> out.txt",
        "2> errors.txt",
        '> "$KB_LANE/lane.log"',
        '> "$KB_LANE/lane.log" 2>&1',
        '&> "$KB_LANE/lane.log"',
        '> out.txt; echo "rc=$?" > "$KB_LANE/lane.rc"',
    ],
)
def test_lane_logging_preserves_authored_stream_redirects(tmp_path: Path, redirect: str):
    stub = tmp_path / "mise"
    stub.write_text(
        '#!/bin/sh\nif [ "$2" = "kb-codex" ]; then\n'
        "echo stdout\necho stderr >&2\nexit 7\nfi\nexit 0\n"
    )
    stub.chmod(0o755)
    source = f"```bash\nmise run kb-codex -- {redirect}\n```\n"
    name = ".claude/agents/kb-codex-advisor.md"
    sites = models_apply.load_sites(Path(__file__).resolve().parents[1] / "models-sites.toml")
    registry = models.load_registry()
    rendered = models_apply.render(name, source, sites, registry)
    assert models_apply.render(name, rendered, sites, registry) == rendered
    block = re.search(r"```bash\n(.*?)```", rendered, re.DOTALL)
    assert block is not None
    result = subprocess.run(
        ["bash", "-c", block[1]],
        cwd=tmp_path,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "KB_LANE": str(tmp_path)},
        check=False,
    )
    assert result.returncode == 7
    if "out.txt" in redirect:
        assert (tmp_path / "out.txt").read_text() == "stdout\n"
        assert (tmp_path / "lane.log").read_text() == "stderr\n"
    elif "errors.txt" in redirect:
        assert (tmp_path / "errors.txt").read_text() == "stderr\n"
        assert (tmp_path / "lane.log").read_text() == "stdout\n"
    else:
        assert (tmp_path / "lane.log").read_text() == "stdout\nstderr\n"
    if "lane.rc" in redirect:
        assert (tmp_path / "lane.rc").read_text() == "rc=7\n"


def test_historical_fences_are_outside_python_docstrings_and_codex_prompts():
    import ast
    import tomllib

    root = Path(__file__).resolve().parents[1]
    for name in ("codex_run.py", "lane_recording.py", "graphify_native_extract.py"):
        source = (root / "python/src/kb_setup" / name).read_text()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                assert "models-apply:" not in (ast.get_docstring(node) or "")
        assert not re.search(r"\\\n\s*# models-apply:", source)
        assert not re.search(r"^#:.*\n# models-apply:.*\n#:", source, re.MULTILINE)
    for path in (root / ".codex/agents").glob("kb-codex-*.toml"):
        assert "models-apply:" not in tomllib.loads(path.read_text())["developer_instructions"]


@pytest.mark.parametrize("info", ["c++", "js title=x", "shell-session"])
@pytest.mark.parametrize("shell_info", ["bash", "bash title=launch"])
def test_n5_arbitrary_fence_info_keeps_next_shell_block_a_site(info, shell_info):
    source = f"```{info}\nexample\n```\n```{shell_info}\ncodex exec -\n```\n"
    rendered = models_apply.render(
        "owned.md", source, models_apply.SitesConfig(), models.load_registry()
    )
    assert "codex exec --strict-config -" in rendered


@pytest.mark.parametrize("name", ["owned.md", "owned.py"])
def test_n6_correct_strict_config_documentation_is_preserved(name):
    source = "Always pass `codex exec --strict-config -s read-only -` here.\n"
    if name.endswith(".py"):
        source = '"""' + source.strip() + '"""\n'
    assert (
        models_apply.render(name, source, models_apply.SitesConfig(), models.load_registry())
        == source
    )


@pytest.mark.parametrize(
    "suffix",
    [
        " &",
        ' | tee "$KB_LANE/lane.log"',
        ' > "$KB_LANE/out.txt"',
        ' >> "$KB_LANE/lane.log"',
        ' &> "$KB_LANE/out.txt"',
    ],
)
def test_n8_lane_shell_shapes_preserve_redirect_and_failure(tmp_path, suffix):
    stub = tmp_path / "mise"
    stub.write_text("#!/bin/sh\necho output\necho warning >&2\nexit 7\n")
    stub.chmod(0o755)
    (tmp_path / "lane.log").write_text("retained\n")
    line = "mise run kb-codex -- --write" + suffix + "\n"
    sites = models_apply.load_sites(Path(__file__).resolve().parents[1] / "models-sites.toml")
    rendered = models_apply._lane_launch_end(line, sites.wrapper_logs[0])
    assert models_apply._lane_launch_end(rendered, sites.wrapper_logs[0]) == rendered
    assert suffix.strip() in rendered
    syntax = subprocess.run(
        ["bash", "-n"], input=rendered, text=True, capture_output=True, check=False
    )
    assert syntax.returncode == 0, syntax.stderr
    env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "KB_LANE": str(tmp_path)}
    result = subprocess.run(
        ["bash", "-c", rendered + 'exit "$rc"\n'], env=env, capture_output=True, check=False
    )
    assert result.returncode == 7, rendered
    if "out.txt" in suffix:
        expected = "output\nwarning\n" if "&>" in suffix else "output\n"
        assert (tmp_path / "out.txt").read_text() == expected
    if ">>" in suffix:
        assert (tmp_path / "lane.log").read_text().startswith("retained\noutput\n")
    if "tee" in suffix or ">>" in suffix:
        assert (tmp_path / "lane.log").exists()
