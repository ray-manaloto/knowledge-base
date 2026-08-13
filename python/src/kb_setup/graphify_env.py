# Copyright (c) 2026 Raymond Manaloto
"""Locate graphify's bundled interpreter.

graphify installs as a pipx tool with its OWN venv python (it can `import
graphify`); the KB repo's uv python cannot. Code that calls graphify's Python API
(e.g. build_merge) must run under this interpreter, not uv's.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tomllib
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
        # NOT clean_env(), on purpose. This is the one subprocess here that is
        # mise itself, and `__MISE_DIFF` is mise's own session state — it reverses
        # the diff to recover the pristine env. Hiding that from mise changes what
        # mise resolves (the same mechanism that made `{{ get_env(name='PATH') }}`
        # launder away every install dir; see `session_path` in launch.py). It
        # also writes nothing: stdout is captured and used as a path, never logged
        # into the corpus, which is the exposure clean_env() exists to close.
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


def pinned_graphify_version(repo_root: Path | None = None) -> str:
    """The version `mise.toml` pins for `pipx:graphifyy`, or `""` when unpinned.

    Reads the file directly rather than importing the currency engine: this is
    one key in one table, and coupling the env module to `currency.config`'s
    ToolSpec loading for it would invert the layering (currency depends on this
    module's resolution helpers, not the other way around).
    """
    root = repo_root or Path.cwd()
    try:
        with (root / "mise.toml").open("rb") as fh:
            data = tomllib.load(fh)
    except OSError, tomllib.TOMLDecodeError:
        return ""
    entry = (data.get("tools") or {}).get("pipx:graphifyy")
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return str(entry.get("version") or "")
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

    Either side being unreadable is reported LOUDLY and not treated as a
    mismatch: an unpinned repo has nothing to enforce, and an exe that cannot
    answer `--version` will fail its real invocation with a better message
    than this gate could synthesize. "Could not compare" is printed as itself
    — never collapsed into either "current" or "drifted" (the currency
    engine's DRIFT/SKIP/OK discipline, applied here).
    """
    root = repo_root or Path.cwd()
    exe = graphify_exe(root)
    pinned = pinned_graphify_version(root)
    running = running_graphify_version(exe)
    if not pinned or not running:
        print(
            f"[graphify] version gate could not compare (pin={pinned or 'UNKNOWN'}, "
            f"running={running or 'UNKNOWN'}, exe={exe}) — proceeding unverified",
            file=sys.stderr,
        )
        return
    if pinned != running:
        raise SystemExit(
            f"[graphify] REFUSING to write the graph with graphify {running} ({exe}) "
            f"while mise.toml pins {pinned}. A stale binary rewriting graph.json is "
            f"how hyperedges were silently destroyed pre-0.9.34, and the carry that "
            f"masked it is retired. Run `mise install`, then retry; "
            f"`mise run kb-currency-check` shows what is stale."
        )


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


def _python_graphify_version(py: Path) -> str:
    """Read the Graphify distribution version from one candidate interpreter."""
    try:
        result = subprocess.run(
            [
                str(py),
                "-c",
                "from importlib.metadata import version; print(version('graphifyy'))",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return ""
    return (result.stdout or "").strip() if result.returncode == 0 else ""


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
        pinned = pinned_graphify_version(root)
        marker_version = _python_graphify_version(cand) if cand.is_file() else ""
        if marker_version and (not pinned or marker_version == pinned) and _imports_graphify(cand):
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
