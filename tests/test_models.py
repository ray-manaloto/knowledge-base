# Copyright (c) 2026 Raymond Manaloto
"""Offline verdict and classifier arms; live catalogs belong to the architect."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import msgspec
import pytest
from kb_setup import models
from kb_setup.generated.models_report import (
    LaunchDecision,
    RegistryReport,
    TrustResult,
    TrustStatus,
    Verdict,
)
from kb_setup.generated.vendor_feeds import Feeds, FeedStatus

_NOW = datetime(2026, 10, 2, tzinfo=UTC)


@pytest.fixture(autouse=True)
def codex_config(tmp_path_factory, monkeypatch) -> Path:
    """Classifier tests must never inherit the host model or project trust."""
    home = tmp_path_factory.mktemp("codex-home")
    home.joinpath("config.toml").write_text(
        f'model = "{models.load_registry().codex.pins["sol"].slug}"\n'
    )
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.chdir(tmp_path_factory.mktemp("codex-project"))
    return home


def _feeds(registry) -> Feeds:
    vendors = {}
    for name, entries in [
        ("codex", registry.codex.known),
        ("agy", registry.agy.known),
        ("claude", registry.claude.known),
    ]:
        feed = models._feed(FeedStatus.LIVE)
        feed.slugs = list(entries)
        feed.efforts = {slug: ["medium", "high", "xhigh"] for slug in entries}
        vendors[name] = feed
    options = {key: registry.agy.pins[role].slug for key, role in models._PLUGIN_ROLES.items()}
    return Feeds(vendors, "claude-opus-5-5[1m]", options, disabled_by_baseline=False, overrides=[])


def _report(registry, feeds, overlay=None) -> RegistryReport:
    return models.evaluate(
        registry, feeds, overlay, TrustResult(TrustStatus.TRUSTED, "fixture", ""), now=_NOW
    )


def test_package_registry_and_spawn_sentinel():
    registry = models.load_registry()
    assert registry.codex.dispatch["kb_codex"].slug == registry.codex.pins["sol"].slug
    assert models.agent_pair("kb-codex-astra-advisor", registry) == (
        registry.codex.pins["astra"].slug,
        None,
    )
    with pytest.raises(ValueError, match="matches 0"):
        models.agent_pair("a-new-unmapped-agent", registry)


def test_pass_drift_overlay_down_and_overlay_add():
    registry = models.load_registry()
    feeds = _feeds(registry)
    assert all(v.verdict == Verdict.OK for v in _report(registry, feeds).vendors)
    feeds.vendors["codex"].slugs.append("fresh-fixture-model-293831")
    assert _report(registry, feeds).vendors[0].verdict == Verdict.NOT_CHECKED
    assert _report(registry, feeds, {}).vendors[0].verdict == Verdict.DRIFT
    assert (
        _report(registry, feeds, {"codex": {"fresh-fixture-model-293831"}}).vendors[0].verdict
        == Verdict.OK
    )


@pytest.mark.parametrize(("hours", "verdict"), [(48, Verdict.INVALID), (96, Verdict.OK)])
def test_retirement_window(hours, verdict):
    registry = models.load_registry()
    feeds = _feeds(registry)
    slug = registry.codex.pins["sol"].slug
    feeds.vendors["codex"].retirements[slug] = (_NOW + timedelta(hours=hours)).isoformat()
    feeds.vendors["codex"].upgrades[slug] = "replacement-fixture"
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == verdict
    assert bool(row.retiring) == (hours == 96)


@pytest.mark.parametrize("key", ["slug", "upgrade", "supported_reasoning_levels"])
def test_codex_shape_fails_loudly_for_each_required_key(key):
    entry = {
        "slug": "fixture",
        "visibility": "list",
        "upgrade": None,
        "supported_reasoning_levels": [{"effort": "high", "future_field": True}],
        "future_field": True,
    }
    assert models.parse_codex(msgspec.json.encode({"models": [entry]})).status == FeedStatus.LIVE
    del entry[key]
    feed = models.parse_codex(msgspec.json.encode({"models": [entry]}))
    assert feed.status == FeedStatus.SHAPE_BROKEN
    assert key in feed.findings[0]


def test_only_stale_launches_are_denied():
    registry = models.load_registry()
    feeds = _feeds(registry)
    sol = registry.codex.pins["sol"].slug
    astra = registry.codex.pins["astra"].slug
    feeds.vendors["codex"].slugs.remove(sol)
    report = _report(registry, feeds)
    for command in [
        "A=b env -i C=d timeout 2 mise exec -- codex exec -",
        "cat a | codex exec -",
        "mise run kb-codex -- --review",
        "echo yes && codex \\\nexec -",
    ]:
        assert not models.classify_launch(
            tool="Bash", command=command, subagent_type=None, report=report
        ).allow
    for command in [
        f"codex exec --model {astra} -",
        f'codex review -c review_model="{astra}"',
        "git status",
        "uv run x",
        'echo "codex exec -"',
        'bash -c "codex exec -"',
    ]:
        assert models.classify_launch(
            tool="Bash", command=command, subagent_type=None, report=report
        ).allow
    assert not models.classify_launch(
        tool="agent.spawn", command=None, subagent_type="kb-codex-advisor", report=report
    ).allow
    assert models.classify_launch(
        tool="Agent", command=None, subagent_type="kb-codex-astra-advisor", report=report
    ).allow
    assert models.classify_launch(
        tool="Edit", command="codex exec -", subagent_type=None, report=report
    ).allow
    feeds.disabled_by_baseline = True
    assert models.classify_launch(
        tool="Bash", command="codex exec -", subagent_type=None, report=_report(registry, feeds)
    ).allow


def test_agy_requires_an_explicit_current_pin():
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["agy"].slugs.remove(registry.agy.pins["flash"].slug)
    report = _report(registry, feeds)
    assert not models.classify_launch(
        tool="Bash", command="agy-delegate.sh --tier flash", subagent_type=None, report=report
    ).allow
    assert models.classify_launch(
        tool="Bash",
        command=f"agy --print --model {registry.agy.pins['pro'].slug}",
        subagent_type=None,
        report=report,
    ).allow


@pytest.mark.parametrize("tool", ["Agent", "agent.spawn"])
def test_claude_agents_pass_while_codex_wrappers_are_denied(tool):
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["codex"].slugs.remove(registry.codex.pins["sol"].slug)
    report = _report(registry, feeds)
    for name in (
        "premise-verifier",
        "kb-synthesist",
        "kb-adversarial-verifier",
        "kb-tool-researcher",
        "kb-corpus-curator",
        "kb-extraction-worker",
    ):
        assert models.classify_launch(
            tool=tool, command=None, subagent_type=name, report=report
        ).allow, name
    assert not models.classify_launch(
        tool=tool, command=None, subagent_type="kb-codex-advisor", report=report
    ).allow


def test_trust_read_is_limited_and_unreadable_is_not_checked(tmp_path: Path):
    config = tmp_path / "config.toml"
    assert models.codex_trust(tmp_path, config).status == TrustStatus.UNREADABLE
    config.write_text(f'[projects."{tmp_path.parent}"]\ntrust_level = "trusted"\n')
    assert models.codex_trust(tmp_path, config).status == TrustStatus.TRUSTED
    config.write_text("[projects]\n")
    result = models.codex_trust(tmp_path, config)
    assert result.status == TrustStatus.UNTRUSTED
    assert 'trust_level = "trusted"' in result.finding
    fix = result.finding.split("user-config fix:\n", 1)[1]
    assert tomllib.loads(fix)["projects"][str(tmp_path)]["trust_level"] == "trusted"


def test_codex_model_forms_alias_and_informational_flags():
    registry = models.load_registry()
    feeds = _feeds(registry)
    sol, astra = (registry.codex.pins[role].slug for role in ("sol", "astra"))
    feeds.vendors["codex"].slugs.remove(sol)
    report = _report(registry, feeds)
    for command in (
        f'codex exec -c model="{astra}" -',
        f"codex e -c 'model=\"{astra}\"' -",
        f"codex exec -m{astra} -",
        "codex exec --help",
        "codex e --version",
        "codex review --help",
        "mise run kb-codex -- --help",
        "agy --print --version",
    ):
        assert models.classify_launch(
            tool="Bash", command=command, subagent_type=None, report=report
        ).allow, command
    for command in ("codex e -", f'codex e -c model="{sol}" -', f"codex exec -m{sol} -"):
        assert not models.classify_launch(
            tool="Bash", command=command, subagent_type=None, report=report
        ).allow, command


def test_naive_retirement_is_shape_broken_and_never_compared():
    registry = models.load_registry()
    slug = registry.codex.pins["sol"].slug
    entry = {
        "slug": slug,
        "visibility": "list",
        "supported_reasoning_levels": [],
        "upgrade": {"model": "replacement", "retirement_at": "2026-10-04T00:00:00"},
    }
    feed = models.parse_codex(msgspec.json.encode({"models": [entry]}))
    assert feed.status == FeedStatus.SHAPE_BROKEN
    assert "retirement_at" in feed.findings[0]
    feeds = _feeds(registry)
    feeds.vendors["codex"] = feed
    assert _report(registry, feeds).vendors[0].verdict == Verdict.NOT_CHECKED
    feeds = _feeds(registry)
    feeds.vendors["codex"].retirements[slug] = entry["upgrade"]["retirement_at"]
    assert _report(registry, feeds).vendors[0].verdict == Verdict.NOT_CHECKED


def test_ship_needs_a_checked_feed_and_no_invalid_pin():
    registry = models.load_registry()
    feeds = _feeds(registry)
    for feed in feeds.vendors.values():
        feed.status = FeedStatus.UNREADABLE
    report = _report(registry, feeds)
    assert models._ship_rc(report) == 1
    for vendor in ("codex", "agy", "claude"):
        feeds.vendors[vendor].status = FeedStatus.LIVE
        assert models._ship_rc(_report(registry, feeds)) == 0
        feeds.vendors[vendor].status = FeedStatus.UNREADABLE
    feeds.vendors["codex"].status = FeedStatus.LIVE
    feeds.vendors["codex"].slugs.remove(registry.codex.pins["sol"].slug)
    assert models._ship_rc(_report(registry, feeds)) == 1
    feeds.disabled_by_baseline = True
    assert models._ship_rc(_report(registry, feeds)) == 0


def test_classifier_cli_owns_its_stdin_snapshot(tmp_path: Path):
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["codex"].slugs.remove(registry.codex.pins["sol"].slug)
    child = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import sys; "
                "from kb_setup.models import main; sys.exit(main(Path.cwd(), sys.argv[1:]))"
            ),
            "classify-launch",
            "--report-json",
            "-",
            "--tool",
            "Agent",
            "--subagent-type",
            "kb-codex-advisor",
        ],
        input=models.encode_report(_report(registry, feeds)),
        text=True,
        capture_output=True,
        cwd=tmp_path,
        check=False,
    )
    assert child.returncode == 0, child.stderr
    assert child.stdout.startswith("DENY: ")
    assert list(tmp_path.iterdir()) == []


def test_cache_rejects_overrides_stale_digest_and_future_time(tmp_path: Path):
    registry = models.load_registry()
    report = _report(registry, _feeds(registry))
    report.checked_at = datetime.now(UTC).isoformat()
    models.write_cache(tmp_path, report)
    assert models.cached_report(tmp_path, registry) is not None
    report.registry_sha256 = "other"
    models.write_cache(tmp_path, report)
    assert models.cached_report(tmp_path, registry) is None
    report.registry_sha256 = registry.registry_sha256
    report.checked_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    models.write_cache(tmp_path, report)
    assert models.cached_report(tmp_path, registry) is None
    feeds = _feeds(registry)
    feeds.overrides = ["registry"]
    assert all(row.verdict != Verdict.OK for row in _report(registry, feeds).vendors)


def test_openrouter_control_shape_and_catalog_disagreement():
    registry = models.load_registry()
    report = _report(registry, _feeds(registry))
    assert not models._catalog_disagreement(report)
    report.vendors[0].unknown_slugs = ["fresh-control-slug-3281"]
    assert models._catalog_disagreement(report)
    assert models._openrouter_ids(b'{"data":[{"id":"openai/fixture","extra":true}]}') == {
        "openai/fixture"
    }
    with pytest.raises(ValueError, match="data"):
        models._openrouter_ids(b'{"data":[{"missing_id":true}]}')
    before = [row.verdict for row in report.vendors]
    assert "budget" in models._control_findings(report, 0)[0]
    assert [row.verdict for row in report.vendors] == before


def _invalid_codex_report(role: str) -> RegistryReport:
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["codex"].slugs.remove(registry.codex.pins[role].slug)
    return _report(registry, feeds)


def _launch(command: str, report: RegistryReport) -> LaunchDecision:
    return models.classify_launch(tool="Bash", command=command, subagent_type=None, report=report)


def test_f4_wrapper_default_is_scoped_to_its_actual_pin():
    report = _invalid_codex_report("astra")
    for command in (
        "kb-codex --write",
        "mise run kb-codex -- --write",
        "mise run codex-lane --",
    ):
        assert _launch(command, report).allow, command
    stale = _launch("kb-codex --review --model gpt-6-astra", report)
    assert not stale.allow
    assert "gpt-6-astra" in stale.reason
    assert "--model" in stale.reason


@pytest.mark.parametrize("argument", ['"$M"', '"${M}"', '"$(cat model.txt)"', '"`cat model.txt`"'])
def test_f4_dynamic_model_is_indeterminate(argument):
    result = _launch(f"codex exec -m {argument} -", _invalid_codex_report("astra"))
    assert not result.allow
    assert "indeterminate" in result.reason
    assert "model" in result.reason


def test_f4_user_config_model_and_privacy(codex_config, capsys):
    config = codex_config / "config.toml"
    original = config.read_bytes()
    config.write_text(config.read_text() + 'private_token = "do-not-emit-this-secret"\n')
    before = config.read_bytes()
    result = _launch("codex exec -", _invalid_codex_report("sol"))
    assert not result.allow
    assert "gpt-6.1-sol" in result.reason
    assert "config.toml" in result.reason
    assert "do-not-emit-this-secret" not in result.reason
    assert capsys.readouterr() == ("", "")
    assert config.read_bytes() == before
    assert before.startswith(original)


@pytest.mark.parametrize("review", ["review", "exec review"])
def test_f4_review_model_overrides_session_model(review, codex_config):
    report = _invalid_codex_report("astra")
    command = f'codex {review} -m gpt-6.1-sol -c review_model="gpt-6-astra"'
    result = _launch(command, report)
    assert not result.allow
    assert "review_model" in result.reason
    assert _launch(f"codex {review} -m gpt-6-astra -c review_model=gpt-6.1-sol", report).allow
    (codex_config / "config.toml").write_text(
        'model = "gpt-6.1-sol"\nreview_model = "gpt-6-astra"\n'
    )
    configured = _launch(f"codex {review}", report)
    assert not configured.allow
    assert "review_model" in configured.reason
    assert _launch("codex exec -", report).allow


def test_f4_model_override_precedence_and_config_forms():
    report = _invalid_codex_report("astra")
    for flag in (
        '-c model="gpt-6-astra"',
        '--config model="gpt-6-astra"',
        '--config=model="gpt-6-astra"',
        '-cmodel="gpt-6-astra"',
    ):
        stale = _launch(f"codex {flag} exec -", report)
        assert not stale.allow
        assert "model" in stale.reason
        assert _launch(f"codex {flag} exec -mgpt-6.1-sol -", report).allow


def test_f4_profile_resolution_and_unreadable_profile(codex_config):
    report = _invalid_codex_report("astra")
    profile = codex_config / "audit.config.toml"
    profile.write_text('model = "gpt-6-astra"\n')
    for flag in ("--profile audit", "--profile=audit", "-p audit"):
        result = _launch(f"codex exec {flag} -", report)
        assert not result.allow
        assert "audit.config.toml" in result.reason
        assert _launch(f"codex exec {flag} -m gpt-6.1-sol -", report).allow
    profile.unlink()
    result = _launch("codex exec --profile audit -", report)
    assert not result.allow
    assert "indeterminate" in result.reason
    assert "profile" in result.reason


def test_f4_project_model_requires_trust(codex_config):
    report = _invalid_codex_report("astra")
    project = Path.cwd()
    (project / ".codex").mkdir()
    (project / ".codex/config.toml").write_text('model = "gpt-6-astra"\n')
    assert _launch("codex exec -", report).allow
    user = codex_config / "config.toml"
    user.write_text(f'model = "gpt-6.1-sol"\n[projects."{project}"]\ntrust_level = "trusted"\n')
    result = _launch("codex exec -", report)
    assert not result.allow
    assert ".codex/config.toml" in result.reason
    (codex_config / "audit.config.toml").write_text('model = "gpt-6.1-sol"\n')
    assert not _launch("codex exec --profile audit -", report).allow
    assert _launch("codex exec -m gpt-6.1-sol -", report).allow


def test_f4_unknown_wrapper_and_missing_model_fail_closed(codex_config):
    report = _invalid_codex_report("astra")
    (codex_config / "config.toml").write_text("[projects]\n")
    for command in ("codex exec -", "mise run kb-codex-unknown -- --write", "codex exec -m"):
        result = _launch(command, report)
        assert not result.allow, command
        assert "indeterminate" in result.reason, command
    assert _launch("mise run kb-codex -- --write", report).allow


def test_f9_bundled_absence_is_not_checked_and_does_not_deny():
    registry = models.load_registry()
    feeds = _feeds(registry)
    feed = feeds.vendors["codex"]
    feed.status = FeedStatus.BUNDLED
    feed.slugs.remove(registry.codex.pins["sol"].slug)
    report = _report(registry, feeds)
    row = report.vendors[0]
    assert row.verdict == Verdict.NOT_CHECKED
    assert row.invalid_pins == {}
    assert any(
        "openai/codex#47152" in finding and "NOT CHECKED" in finding for finding in row.findings
    )
    assert _launch("codex exec -", report).allow
    assert models.classify_launch(
        tool="Agent", command=None, subagent_type="kb-codex-advisor", report=report
    ).allow
    for name in ("agy", "claude"):
        feeds.vendors[name].status = FeedStatus.UNREADABLE
    assert models._ship_rc(_report(registry, feeds)) == 1


@pytest.mark.parametrize("status", [FeedStatus.BUNDLED, FeedStatus.LIVE])
def test_f9_native_retirement_remains_positive_evidence(status):
    registry = models.load_registry()
    feeds = _feeds(registry)
    slug = registry.codex.pins["astra"].slug
    feed = feeds.vendors["codex"]
    feed.status = status
    feed.retirements[slug] = (_NOW + timedelta(hours=48)).isoformat()
    feed.upgrades[slug] = "replacement-fixture"
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == Verdict.INVALID
    assert row.invalid_pins == {"astra": slug}


def test_f9_live_absence_is_invalid_and_bundled_presence_is_not_a_check():
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["codex"].slugs.remove(registry.codex.pins["astra"].slug)
    assert _report(registry, feeds).vendors[0].verdict == Verdict.INVALID
    feeds = _feeds(registry)
    feeds.vendors["codex"].status = FeedStatus.BUNDLED
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == Verdict.NOT_CHECKED
    assert not row.invalid_pins


def test_f9_hidden_bundled_retirement_is_positive_evidence():
    registry = models.load_registry()
    slug = registry.codex.pins["astra"].slug
    entry = {
        "slug": slug,
        "visibility": "hide",
        "supported_reasoning_levels": [{"effort": "xhigh"}],
        "upgrade": {
            "model": "replacement-fixture",
            "retirement_at": (_NOW + timedelta(hours=48)).isoformat(),
        },
    }
    feeds = _feeds(registry)
    feeds.vendors["codex"] = models.parse_codex(
        msgspec.json.encode({"models": [entry]}), FeedStatus.BUNDLED
    )
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == Verdict.INVALID
    assert row.invalid_pins == {"astra": slug}


def test_f9_live_absence_wins_over_a_future_retirement_marker():
    registry = models.load_registry()
    feeds = _feeds(registry)
    slug = registry.codex.pins["astra"].slug
    feed = feeds.vendors["codex"]
    feed.slugs.remove(slug)
    feed.retirements[slug] = (_NOW + timedelta(hours=96)).isoformat()
    feed.upgrades[slug] = "replacement-fixture"
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == Verdict.INVALID
    assert row.invalid_pins == {"astra": slug}


def test_n4_profile_cannot_bypass_indeterminate_project_trust(codex_config):
    (codex_config / "audit.config.toml").write_text('model = "gpt-6.1-sol"\n')
    (codex_config / "config.toml").write_text('private_token = "do-not-emit-this-secret')
    report = _invalid_codex_report("astra")
    assert not _launch("codex exec --profile audit -", report).allow
    unresolved = _launch("codex exec -", report)
    assert not unresolved.allow
    assert "config.toml" in unresolved.reason
    assert "indeterminate" in unresolved.reason
    assert "do-not-emit-this-secret" not in unresolved.reason


@pytest.mark.parametrize(
    "task",
    [
        "kb-codex-config-check",
        "codex-log-check",
        "codex-agent-parity",
        "codex-agent-validate",
        "codex-lane-mirror",
        "codex-schema-generate",
        "codex-schema-check",
    ],
)
def test_f4_unknown_wrappers_do_not_block_codex_repair(task):
    report = _invalid_codex_report("astra")
    assert _launch(f"mise run {task} -- lane.log", report).allow


@pytest.mark.parametrize(
    "wrapper",
    ["kb-codex", "mise run kb-codex --", "mise run codex-lane --", "mise run sdlc-team --"],
)
@pytest.mark.parametrize("mode", ["--write", "--review"])
def test_n1_wrapper_emitted_pin_outranks_user_model(wrapper, mode, codex_config):
    (codex_config / "config.toml").write_text(
        'model = "gpt-6-astra"\nreview_model = "gpt-6-astra"\n'
    )
    command = f"{wrapper} {mode}"
    result = _launch(command, _invalid_codex_report("sol"))
    assert not result.allow
    assert "gpt-6.1-sol" in result.reason
    assert "wrapper" in result.reason
    assert _launch(command, _invalid_codex_report("astra")).allow
    (codex_config / "config.toml").write_text('model = "unterminated')
    assert _launch(command, _invalid_codex_report("astra")).allow


def _catalog_entry(slug, visibility="list", upgrade=None) -> dict:
    return {
        "slug": slug,
        "visibility": visibility,
        "upgrade": upgrade,
        "supported_reasoning_levels": [{"effort": e} for e in ("medium", "high", "xhigh")],
    }


@pytest.mark.parametrize("overlay", [None, {}])
def test_n2_hidden_models_are_present_without_catalog_drift(overlay):
    registry = models.load_registry()
    entries = [_catalog_entry(pin.slug, "hide") for pin in registry.codex.pins.values()]
    entries += [_catalog_entry("gpt-reserve", "hide"), _catalog_entry("codex-auto-review", "hide")]
    feeds = _feeds(registry)
    feeds.vendors["codex"] = models.parse_codex(msgspec.json.encode({"models": entries}))
    row = _report(registry, feeds, overlay).vendors[0]
    assert row.verdict == Verdict.OK
    assert row.unknown_slugs == []
    assert row.invalid_pins == {}


def test_n3_successful_debug_models_without_freshness_is_not_live(tmp_path, monkeypatch):
    # Exercise the subprocess boundary with an isolated executable, never Codex.
    payload = tmp_path / "catalog.json"
    payload.write_bytes(msgspec.json.encode({"models": []}))
    stub = tmp_path / "mise"
    stub.write_text(f'#!/bin/sh\ncat "{payload}"\necho refresh-failed >&2\n')
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:/usr/bin:/bin")
    feed = models._codex_feed()
    assert feed.status == FeedStatus.BUNDLED
    assert any("unverified-live" in line for line in feed.findings)
    assert any("refresh-failed" in line for line in feed.findings)
    registry = models.load_registry()
    feeds = _feeds(registry)
    feeds.vendors["codex"] = feed
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == Verdict.NOT_CHECKED
    assert not row.invalid_pins


def test_n7_disabled_ship_check_is_loud_and_offline(tmp_path, capsys):
    baseline = tmp_path / "doctor.toml"
    baseline.write_text("[models]\nenabled = false\n")
    assert models.main(tmp_path, ["ship-check", "--baseline", str(baseline)]) == 0
    assert "models gate DISABLED by doctor.toml" in capsys.readouterr().out


@pytest.mark.parametrize("hours", [72, 73, 432])
def test_n10_native_marker_window(hours):
    registry = models.load_registry()
    slug = registry.codex.pins["sol"].slug
    entries = [_catalog_entry(pin.slug) for pin in registry.codex.pins.values()]
    entries[0]["upgrade"] = {
        "model": "replacement",
        "retirement_at": (_NOW + timedelta(hours=hours)).isoformat(),
    }
    assert entries[0]["slug"] == slug
    feeds = _feeds(registry)
    feeds.vendors["codex"] = models.parse_codex(msgspec.json.encode({"models": entries}))
    row = _report(registry, feeds).vendors[0]
    assert row.verdict == (Verdict.INVALID if hours == 72 else Verdict.OK)
    assert bool(row.retiring) == (hours > 72)


def test_n11_any_trusted_ancestor_wins(codex_config):
    root = Path.cwd()
    (root / ".codex").mkdir()
    (root / ".codex/config.toml").write_text('model = "gpt-6-astra"\n')
    config = codex_config / "config.toml"
    config.write_text(
        f'model = "gpt-6.1-sol"\n[projects."{root}"]\ntrust_level = "untrusted"\n'
        f'[projects."{root.parent}"]\ntrust_level = "trusted"\n'
    )
    assert models.codex_trust(root, config).status == TrustStatus.TRUSTED
    assert not _launch("codex exec -", _invalid_codex_report("astra")).allow


def test_n11_main_clone_trust_applies_to_real_worktree(tmp_path, codex_config):
    main, worktree = tmp_path / "clone", tmp_path / "worktree"
    subprocess.run(["git", "init", "-q", str(main)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(main),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.com",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "fixture",
        ],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(main), "worktree", "add", "-q", "-b", "fixture", str(worktree)],
        check=True,
    )
    (worktree / ".codex").mkdir()
    (worktree / ".codex/config.toml").write_text('model = "gpt-6-astra"\n')
    config = codex_config / "config.toml"
    config.write_text(f'model = "gpt-6.1-sol"\n[projects."{main}"]\ntrust_level = "trusted"\n')
    assert models.codex_trust(worktree, config).status == TrustStatus.TRUSTED
    result = models.classify_launch(
        tool="Bash",
        command="codex exec -",
        subagent_type=None,
        report=_invalid_codex_report("astra"),
        root=worktree,
    )
    assert not result.allow


@pytest.mark.parametrize(
    "command",
    [
        "echo it's; codex exec -m gpt-6-astra -",
        "cat <<'EOF' | codex exec -m gpt-6-astra -\nWe don't know whether option A is safe.\nEOF",
    ],
)
def test_n12_unparsable_codex_command_is_indeterminate(command):
    result = _launch(command, _invalid_codex_report("astra"))
    assert not result.allow
    assert "indeterminate" in result.reason
    assert _launch(command, _report(models.load_registry(), _feeds(models.load_registry()))).allow
    assert _launch("echo it's", _invalid_codex_report("astra")).allow


@pytest.mark.parametrize(
    "prefix", ["CODEX_HOME={home} ", "env CODEX_HOME={home} ", "CODEX_HOME={home} mise exec -- "]
)
def test_n13_command_scoped_codex_home(tmp_path, prefix):
    home = tmp_path / "other-home"
    home.mkdir()
    (home / "config.toml").write_text('model = "gpt-6-astra"\n')
    command = prefix.format(home=home) + "codex exec -"
    assert not _launch(command, _invalid_codex_report("astra")).allow
    assert _launch(command, _invalid_codex_report("sol")).allow
    assert _launch("codex exec -", _invalid_codex_report("astra")).allow


@pytest.mark.parametrize(
    "command",
    [
        "codex -C {project} exec -",
        "codex exec --cd={project} -",
        "cd {project} && codex exec -",
        "cd {project}\ncodex exec -",
    ],
)
def test_n13_command_working_directory(tmp_path, codex_config, command):
    project = tmp_path / "other-project"
    (project / ".codex").mkdir(parents=True)
    (project / ".git").mkdir()
    (project / ".codex/config.toml").write_text('model = "gpt-6-astra"\n')
    (codex_config / "config.toml").write_text(
        f'model = "gpt-6.1-sol"\n[projects."{project}"]\ntrust_level = "trusted"\n'
    )
    assert not _launch(command.format(project=project), _invalid_codex_report("astra")).allow
    assert _launch(command.format(project=project), _invalid_codex_report("sol")).allow


@pytest.mark.parametrize(
    "command",
    [
        'CODEX_HOME="$UNRESOLVED" codex exec -',
        'codex -C "$UNRESOLVED" exec -',
        'cd "$UNRESOLVED" && codex exec -',
        "codex -C /no-such-model-registry-project-23881 exec -",
    ],
)
def test_n13_unresolvable_context_is_indeterminate(command):
    result = _launch(command, _invalid_codex_report("astra"))
    assert not result.allow
    assert "indeterminate" in result.reason
