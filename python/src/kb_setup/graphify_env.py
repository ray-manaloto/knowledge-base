"""Locate graphify's bundled interpreter.

graphify installs as a pipx tool with its OWN venv python (it can `import
graphify`); the KB repo's uv python cannot. Code that calls graphify's Python API
(e.g. build_merge) must run under this interpreter, not uv's.
"""

from __future__ import annotations

import os
import shutil
import subprocess
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


def clean_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A copy of os.environ with every non-Claude backend trigger removed.

    Use for EVERY graphify subprocess. With these stripped, graphify's
    detect_backend() finds nothing (unless ANTHROPIC_API_KEY is set, which is the
    Claude path we keep) and labeling uses the deterministic no-LLM hub labeler —
    never Gemini/Bedrock/etc., and with no failed backend attempts. Pass ``extra``
    to set additional vars.
    """
    env = {k: v for k, v in os.environ.items() if k not in _STRIP_BACKEND_ENV}
    if extra:
        env.update(extra)
    return env


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
    """Return a path to an interpreter that can ``import graphify``.

    Resolution order: the marker graphify writes (``graphify-out/.graphify_python``),
    then ``mise where pipx:graphifyy`` → ``**/bin/python``, then the ``graphify``
    binary's sibling. Raises if none can import graphify.
    """
    root = repo_root or Path.cwd()

    marker = root / "graphify-out" / ".graphify_python"
    if marker.is_file():
        cand = Path(marker.read_text(encoding="utf-8").strip())
        if cand.is_file() and _imports_graphify(cand):
            return str(cand)

    try:
        out = subprocess.run(
            ["mise", "where", "pipx:graphifyy"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        base = Path(out.stdout.strip())
        for cand in sorted(base.glob("**/bin/python")):
            if _imports_graphify(cand):
                return str(cand)
    except OSError, subprocess.SubprocessError:
        pass

    exe = shutil.which("graphify")
    if exe:
        cand = Path(exe).resolve().parent / "python"
        if cand.is_file() and _imports_graphify(cand):
            return str(cand)

    raise RuntimeError(
        "could not locate graphify's bundled interpreter — is `graphify` installed (mise install)?"
    )


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
