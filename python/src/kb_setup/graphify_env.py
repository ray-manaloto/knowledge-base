"""Locate graphify's bundled interpreter.

graphify installs as a pipx tool with its OWN venv python (it can `import
graphify`); the KB repo's uv python cannot. Code that calls graphify's Python API
(e.g. build_merge) must run under this interpreter, not uv's.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

#: One-shot latches for warnings that would otherwise repeat per call.
_WARNED: set[str] = set()

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


def graphify_exe(repo_root: Path | None = None) -> str:
    """The graphify binary to invoke — resolved through mise, never by PATH order.

    WHY NOT A BARE ``"graphify"``. PATH ordering inside a live session is not ours
    to control, and the launcher's cleaning does not necessarily reach it.
    Measured 2026-07-27 with a three-way sentinel probe (#40): tmux hands a new
    pane the **client's** PATH and discards ``new-session -e PATH=…`` — the
    injected value is stored in the session environment (``show-environment``
    confirms it) but is not what the pane's process gets. Control arms: ``-e
    FOOBAR=…`` in the same pane arrived intact, so ``-e`` is not broken in
    general, only overridden for PATH; and the probe's command was ``/bin/sh -c``,
    which sources no profile, so the login shell is not the re-adder either.

    The consequence is concrete: a frozen ``mise/installs/<tool>/<ver>/bin`` entry
    can sit ahead of the shims *inside* a session that passed preflight, and
    :func:`kb_setup.graph.build` stamps the corpus with the **pinned** version
    regardless of which binary actually ran. A graph built by one version and
    stamped another is unfalsifiable afterwards — the one failure this repo
    cannot absorb.

    ``mise which`` answers from mise's config for ``repo_root``, so it follows the
    pin by construction and is indifferent to where an entry sits on PATH. The
    ``shutil.which`` fallback keeps a mise-less machine working; it restores the
    old PATH-ordered behaviour, which is worse but never worse than failing.
    """
    root = repo_root or Path.cwd()
    try:
        out = subprocess.run(
            ["mise", "which", "graphify"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
            cwd=root,
        )
    except OSError, subprocess.SubprocessError:
        pass
    else:
        # `or ""`: a CompletedProcess carries stdout=None whenever the call was not
        # capturing, so this must not assume a string. Reached in practice by any
        # caller that patches subprocess.run for its own reasons.
        resolved = (out.stdout or "").strip()
        if resolved and Path(resolved).is_file():
            return resolved
    # Not an error — a machine without mise still has a working graphify on PATH
    # — but it IS a downgrade to the behaviour this function exists to replace,
    # so it says so. Silence here would make the degradation invisible in a build
    # log, which is the same "could not check, rendered as fine" collapse the
    # currency engine refuses to make. Warned once per process: the artifact path
    # resolves per output and would otherwise print eight times.
    # A set that is MUTATED rather than a flag that is rebound: rebinding a
    # module global would need a `global` statement, and silencing the resulting
    # lint would need an inline suppression, which this repo rejects outright.
    fallback = shutil.which("graphify")
    if "fallback" not in _WARNED:
        _WARNED.add("fallback")
        print(
            f"[graphify] WARNING: `mise which graphify` gave no answer; falling back to "
            f"{fallback or 'the bare name `graphify`'} resolved through PATH. That does "
            f"NOT follow this repo's pin — run `mise run cc-doctor`.",
            file=sys.stderr,
        )
    return fallback or "graphify"


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
            # cwd=root, not the process cwd: `mise where` answers for the config
            # it finds from the CWD, so without this the function silently
            # ignored the repo_root it was handed and could return a DIFFERENT
            # version's interpreter than the caller asked about. Measured: from
            # the repo it answers 0.9.26, from /tmp it answers 0.9.28. That lands
            # on corpus-WRITING paths (kb-merge's build_merge, kb-build's doc
            # replay), so it is not cosmetic.
            cwd=root,
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
