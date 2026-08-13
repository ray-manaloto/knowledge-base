# Copyright (c) 2026 Raymond Manaloto
"""Resolve the Graphify CLI and SDK from the repository's locked uv environment."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# Env vars graphify's `detect_backend()` keys off, in its priority order:
#   gemini -> kimi -> claude -> openai -> deepseek -> azure -> bedrock -> ollama.
# This KB is "Claude Code only" (Ray, 2026-07-22): all LLM work is Claude (the
# host-agent Workflow for extraction) or a deterministic no-LLM path (labeling).
# We strip EVERY non-Claude trigger from every graphify subprocess so detect_backend
# returns None -> graphify uses its deterministic hub labeler with NO failing
# backend attempts. Stripping only Gemini was not enough: detect_backend then fell
# to Bedrock (AWS_REGION was set) and spewed 25 failed "Converse" batches before the
# deterministic fallback. ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL are intentionally
# KEPT — that is the Claude path, and the claude API backend (unlike the broken
# claude-cli one, #2076) parses fine. See CLAUDE.md, the kb-label task, and
# `.claude/skills/kb-curator`.
_STRIP_BACKEND_ENV = (
    # gemini / google
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    # kimi / moonshot
    "KIMI_API_KEY",
    "MOONSHOT_API_KEY",
    # openai + other openai-compat providers
    "OPENAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
    # azure
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_API_KEY",
    # bedrock (any of these flips detect_backend to bedrock)
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    # ollama
    "OLLAMA_BASE_URL",
    "OLLAMA_HOST",
)

# A SECOND, unrelated reason to strip — do not merge this into the tuple above.
# Everything in _STRIP_BACKEND_ENV goes because it would flip graphify's
# detect_backend(); mise is not a backend and never could be. These go because
# they SMUGGLE THE VALUES the list above removes by name.
#
# `__MISE_DIFF` is mise's env snapshot: gzip + base64 + msgpack, carrying the
# full new/old env maps — every value mise's `[env]` resolved, including
# SOPS/age-decrypted secrets. So stripping `AWS_SECRET_ACCESS_KEY` by name while
# leaving `__MISE_DIFF` beside it removes the label and keeps the contents. Two
# things make it worse than an ordinary variable: gitleaks cannot pattern-match a
# gzip'd blob, and mise's own redaction is a *stdout line filter*
# (`docs/environments/index.md:170`) that never touches the environment handed to
# a child. v2026.5.6 widened the blast radius by propagating it to children. This
# is expected upstream behaviour with no fix pending — evidence, control arms and
# the release-note sweep in `docs/research/reports/mise-path-research.md` § Q4.
#
# A PREFIX and not a name list, deliberately. A name list is a token-spelling
# bound (`probes-need-a-control-arm.md`): it protects against the two blobs that
# exist today and silently fails open the day mise adds a third. `__MISE_` is
# mise's private namespace — the same report measured `__MISE_ORIG_PATH` at 0
# hits across mise's `docs/` (vs 32-file controls), i.e. `__`-prefixed means
# internal and unsupported. The known members are `__MISE_DIFF` and
# `__MISE_SESSION`; the rest is shell-activation bookkeeping a graphify
# subprocess has no use for either.
#
# The doubled underscore is load-bearing: PUBLIC mise config is `MISE_*` with one
# underscore (`MISE_DATA_DIR`, which `kb_setup.currency.sync` reads), and
# stripping that would break real configuration. Arm both directions when
# changing this.
_STRIP_MISE_ENV_PREFIX = "__MISE_"


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of os.environ with backend triggers AND mise's secret blob removed.

    Use for EVERY graphify subprocess. Two independent strips, for two unrelated
    reasons (see the comments on each constant): `_STRIP_BACKEND_ENV` stops
    graphify's detect_backend() picking a non-Claude backend, so labeling uses the
    deterministic no-LLM hub labeler with no failed backend attempts;
    `_STRIP_MISE_ENV_PREFIX` stops mise's `__MISE_DIFF` carrying the *values* of
    the credentials the first list removes by *name* into a process that writes
    the corpus. Pass ``extra`` to set additional vars.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in _STRIP_BACKEND_ENV and not k.startswith(_STRIP_MISE_ENV_PREFIX)
    }
    if extra:
        env.update(extra)
    return env


def graphify_exe(repo_root: Path | None = None) -> str:
    """Return the uv-synced Graphify executable, never a global or mise pipx copy."""
    root = repo_root or Path.cwd()
    candidate = root / ".venv" / "bin" / "graphify"
    return str(candidate)


def pinned_graphify_version(repo_root: Path | None = None) -> str:
    """Return the exact ``graphifyy[all]`` project requirement, or ``""``."""
    root = repo_root or Path.cwd()
    try:
        with (root / "pyproject.toml").open("rb") as fh:
            data = tomllib.load(fh)
    except OSError, tomllib.TOMLDecodeError:
        return ""
    dependencies = (data.get("project") or {}).get("dependencies") or []
    for requirement in dependencies:
        match = re.fullmatch(r"graphifyy\[all\]==([0-9]+(?:\.[0-9]+)+)", str(requirement))
        if match:
            return match.group(1)
    return ""


def running_graphify_version(exe: str) -> str:
    """`<exe> --version`'s version token, or `""` when it cannot be asked.

    graphify prints `graphify <version>`; the first dotted-number run is the
    token, so a wrapper that prepends chatter still parses. `""` means the
    question was never answered — the caller must not read it as a version.
    """
    try:
        proc = subprocess.run(
            [exe, "--version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
            env=clean_env(),
        )
    except OSError, subprocess.SubprocessError:
        return ""
    text = ((proc.stdout or "") + " " + (proc.stderr or "")).strip()
    m = re.search(r"\b(\d+\.\d+\.\d+(?:\.\d+)?)\b", text)
    return m.group(1) if m else ""


def assert_pinned_graphify(repo_root: Path | None = None) -> None:
    """Refuse to let a graph WRITER run a graphify other than the pinned one.

    Exists because the hyperedge carry was retired at 0.9.34 (cold lane on
    #186, P1): `graphify_exe`'s PATH fallback can still hand back a stale
    binary — live on this host, where bare `graphify` resolved to 0.9.32 under
    a 0.9.34 pin — and a pre-0.9.34 `label`/`cluster-only` silently empties the
    graph's hyperedges with no carry left to restore them, after which the
    restamp asserts success. For a READER a stale binary is a worse answer;
    for a WRITER it is destroyed data, so the writer tasks call this and
    refuse (`SystemExit`) on a mismatch, naming both versions and the remedy.

    Either side being unreadable is a refusal. UNKNOWN cannot authorize an
    operation over the graph.
    """
    root = repo_root or Path.cwd()
    exe = graphify_exe(root)
    pinned = pinned_graphify_version(root)
    running = running_graphify_version(exe)
    if not pinned or not running:
        raise SystemExit(
            f"[graphify] REFUSING an unverified Graphify operation "
            f"(pin={pinned or 'UNKNOWN'}, running={running or 'UNKNOWN'}, exe={exe}). "
            "Run `mise deps` to restore the locked uv environment."
        )
        return
    if pinned != running:
        raise SystemExit(
            f"[graphify] REFUSING to write the graph with graphify {running} ({exe}) "
            f"while pyproject.toml pins {pinned}. A stale binary rewriting graph.json is "
            f"how hyperedges were silently destroyed pre-0.9.34, and the carry that "
            f"masked it is retired. Run `mise deps`, then retry; "
            f"`mise run kb-currency-check` shows what is stale."
        )
    from kb_setup.graphify_sdk import assert_public_sdk

    assert_public_sdk(pinned)


def _imports_graphify(py: Path) -> bool:
    try:
        return (
            subprocess.run(
                [str(py), "-c", "import graphify"], capture_output=True, timeout=30, check=False
            ).returncode
            == 0
        )
    except OSError, subprocess.SubprocessError:
        return False


def graphify_python(repo_root: Path | None = None) -> str:
    """Return the uv-synced interpreter after proving it imports Graphify."""
    root = repo_root or Path.cwd()
    candidate = root / ".venv" / "bin" / "python"
    if candidate.is_file() and _imports_graphify(candidate):
        return str(candidate)
    running = Path(sys.executable)
    if _imports_graphify(running):
        return str(running)
    raise RuntimeError("locked Graphify SDK is unavailable — run `mise deps`")


# Runtime deps some graphify outputs need that its packaging does NOT pull on
# Python 3.14. On 3.12 scipy arrives transitively via graspologic (the leiden
# extra); on 3.14 graspologic is skipped, so `export svg` (nx.spring_layout →
# scipy) breaks. We inject it idempotently. Maps import-name -> pip-spec.
_OUTPUT_DEPS: dict[str, str] = {"scipy": "scipy"}


def ensure_runtime_deps(repo_root: Path | None = None) -> list[str]:
    """Idempotently install output-only runtime deps missing from graphify's env.

    Returns the list of packages it installed (empty if all present). Safe to call
    before every artifact run — a no-op once satisfied.
    """
    py = graphify_python(repo_root)
    installed: list[str] = []
    for mod, spec in _OUTPUT_DEPS.items():
        if _imports(py, mod):
            continue
        print(f"[deps] graphify env missing {mod!r} — injecting {spec}")
        subprocess.run(["uv", "pip", "install", "--python", py, spec], check=True, timeout=600)
        installed.append(spec)
    return installed


def _imports(py: str, module: str) -> bool:
    try:
        return (
            subprocess.run(
                [py, "-c", f"import {module}"], capture_output=True, timeout=30, check=False
            ).returncode
            == 0
        )
    except OSError, subprocess.SubprocessError:
        return False
