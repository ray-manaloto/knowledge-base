# Copyright (c) 2026 Raymond Manaloto
"""Real wiring tokens, each with its own sharp deletion arm on a scratch copy."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pytest
from kb_setup import claude_types

_ROOT = Path(__file__).resolve().parents[1]
_TOKENS = [
    ("hk.pkl", '["models_apply"]'),
    ("hk.pkl", 'check = "uv run kb-setup models apply --check --sites models-sites.toml"'),
    ("hk.pkl", '["fnhook_gates"]'),
    ("hk.pkl", 'check = "uv run kb-setup fnhook-gates"'),
    ("python/src/kb_setup/cli.py", 'if cmd == "models":'),
    ("python/src/kb_setup/models.py", 'if argv and argv[0] == "apply":'),
    ("python/src/kb_setup/cli.py", 'if cmd == "fnhook-gates":'),
    ("python/src/kb_setup/cli.py", 'if cmd in {"claude-types-refresh", "claude-types-check"}:'),
    ("python/src/kb_setup/cli.py", 'if cmd == "codex-log-check":'),
    ("python/src/kb_setup/gates.py", '"kb-models-ship-check",'),
    ("python/src/kb_setup/gates.py", '"fnhook-gates",'),
]
_RUNS = {
    "models-apply": "uv run kb-setup models apply --sites models-sites.toml",
    "models-check": "uv run kb-setup models check --baseline doctor.toml",
    "models-classify": "uv run kb-setup models classify-launch",
    "kb-models-ship-check": "uv run kb-setup models ship-check --baseline doctor.toml",
    "fnhook-gates": "uv run kb-setup fnhook-gates",
    "claude-types-refresh": "uv run kb-setup claude-types-refresh",
    "codex-log-check": "uv run kb-setup codex-log-check",
}


@pytest.mark.parametrize(("name", "token"), _TOKENS)
def test_real_token_and_sharp_deletion(name: str, token: str, tmp_path: Path):
    def check(root: Path) -> None:
        assert token in (root / name).read_text()

    check(_ROOT)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text((_ROOT / name).read_text().replace(token, ""))
    with pytest.raises(AssertionError):
        check(tmp_path)


@pytest.mark.parametrize(("task", "run"), _RUNS.items())
def test_task_run_and_deletion(task: str, run: str, tmp_path: Path):
    def check(path: Path) -> None:
        data = tomllib.loads(path.read_text())
        assert data["tasks"][task]["run"] == run

    check(_ROOT / "mise.toml")
    text = (_ROOT / "mise.toml").read_text()
    path = tmp_path / "mise.toml"
    path.write_text(text.replace(f'run = "{run}"', 'run = "deleted-call-site"'))
    with pytest.raises(AssertionError):
        check(path)


def test_baseline_and_deletion(tmp_path: Path):
    def check(path: Path) -> None:
        assert tomllib.loads(path.read_text()).get("models", {}).get("enabled") is True

    check(_ROOT / "doctor.toml")
    path = tmp_path / "doctor.toml"
    path.write_text("[models]\n")
    with pytest.raises(AssertionError):
        check(path)


@pytest.mark.parametrize(
    "plugin", ["python/src/kb_setup/plugins/model-registry", ".claude/skills/model-registry"]
)
def test_hooks_module_and_deletion(plugin: str, tmp_path: Path):
    def check(path: Path) -> None:
        assert json.loads(path.read_text())["modules"] == ["./register.ts"]

    check(_ROOT / plugin / "hooks/hooks.json")
    path = tmp_path / "hooks.json"
    path.write_text('{"modules": []}\n')
    with pytest.raises(AssertionError):
        check(path)


def test_claude_pin_and_row_deletion(tmp_path: Path):
    pin = claude_types.load_pin(_ROOT)
    assert pin.version
    assert pin.source
    assert pin.sha256
    path = tmp_path / "schemas/sources.toml"
    path.parent.mkdir(parents=True)
    path.write_text("schema = []\n")
    with pytest.raises(ValueError, match="exactly one claude-code row"):
        claude_types.load_pin(tmp_path)


def test_models_apply_covers_any_staged_path():
    source = (_ROOT / "hk.pkl").read_text()
    step = source.split('["models_apply"] = new Step {', 1)[1].split("\n  }", 1)[0]
    assert 'glob = "**/*"' in step
    assert 'glob = "**/*"' not in step.replace('glob = "**/*"', 'glob = "models-sites.toml"')


def test_hook_snapshots_use_stdin_without_state_files():
    for plugin in ("python/src/kb_setup/plugins/model-registry", ".claude/skills/model-registry"):
        source = (_ROOT / plugin / "hooks/register.ts").read_text()
        assert '"--report-json", "-"' in source
        assert "stdin: snapshot" in source
        assert "$.fs.write" not in source
        assert "model-registry-hook-" not in source
