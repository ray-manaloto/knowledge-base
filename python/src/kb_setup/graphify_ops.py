"""Single-source graphify operations: merge a doc chunk, label, transcribe.

Each is wrapped by a mise task (kb-merge / kb-label / kb-transcribe) so NOTHING
calls graphify by hand — the PreToolUse guard (`kb_setup.hook_guard`) denies raw
`graphify …` / `_merge_docs.py` invocations and redirects here.

Every graphify subprocess runs under `graphify_env.clean_env()`, which strips
non-Claude provider keys — so labeling can only use the claude-cli backend (your
Claude Pro/Max subscription) or the deterministic no-LLM fallback, never an
auto-detected Gemini/OpenAI key.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from kb_setup.graphify_env import clean_env, graphify_python

_MERGE_SCRIPT = Path(__file__).with_name("_merge_docs.py")


def merge_chunk(repo_root: Path, chunk: str, root: str | None = None) -> int:
    """Merge one host-agent extraction chunk into graphify-out/graph.json.

    Runs `_merge_docs.py` under graphify's bundled interpreter (it imports
    graphify) with a Gemini-free env. `root` is the source root for path
    relativization (defaults to the chunk's dir; moot for URL-sourced chunks).
    """
    chunk_path = Path(chunk)
    if not chunk_path.is_file():
        print(f"[kb-merge] no such chunk: {chunk}", file=sys.stderr)
        return 2
    out = repo_root / "graphify-out" / "graph.json"
    src_root = root or str(chunk_path.resolve().parent)
    gpy = graphify_python(repo_root)
    cmd = [gpy, str(_MERGE_SCRIPT), str(chunk_path), src_root, str(out)]
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode


def label(repo_root: Path, *, missing_only: bool = False, claude_cli: bool = False) -> int:
    """(Re)label communities WITHOUT Gemini.

    Default = graphify's deterministic, LLM-free hub-name labeler (names each
    community after its highest-degree member). Instant, no API, no Gemini.

    Why deterministic is the default (Ray, 2026-07-22, control-arm verified): the
    only LLM path that is NOT Gemini is graphify's `claude-cli` backend, and that
    backend is BROKEN for labeling (issue #2076) — the CLI returns prose-wrapped
    JSON ("Done — cluster names above …") that graphify cannot parse, so every
    batch fails and the run is slow + noisy for no gain. `--claude-cli` still opts
    into it (falls back to deterministic on the inevitable failure), kept only so a
    future graphify fix can be re-probed through the task. clean_env() strips
    GEMINI/GOOGLE either way, so Gemini can never be auto-selected.
    """
    if not shutil.which("graphify"):
        print("[kb-label] graphify not on PATH — run `mise install`", file=sys.stderr)
        return 2

    base = ["graphify", "label", "."]
    if missing_only:
        base.append("--missing-only")

    def _run(cmd: list[str], why: str) -> int:
        print(f"  $ {' '.join(cmd)}   # {why}")
        return subprocess.run(cmd, cwd=repo_root, env=clean_env(), check=False).returncode

    if not claude_cli:
        # No --backend + GEMINI/GOOGLE stripped -> auto-detect finds nothing ->
        # deterministic hub labeler. The clean default.
        return _run(base, "deterministic no-LLM hub labels (Gemini-free)")

    rc = _run(
        [*base, "--backend=claude-cli", "--max-concurrency=1"],
        "claude-cli backend (opt-in; broken #2076 — expect fallback)",
    )
    if rc == 0:
        return 0
    print(
        "[kb-label] claude-cli backend failed (#2076) — deterministic no-LLM fallback.",
        file=sys.stderr,
    )
    return _run(base, "deterministic fallback")


def transcribe(repo_root: Path, audio: str) -> int:
    """Transcribe a local audio file with graphify's bundled faster-whisper.

    Local, no API key, no LLM backend (e.g. a graphify-downloaded yt_*.m4a). Prints
    the transcript path. Extraction of the transcript into the graph is then the
    normal host-agent (Claude Code) step.
    """
    audio_path = Path(audio)
    if not audio_path.is_file():
        print(f"[kb-transcribe] no such audio file: {audio}", file=sys.stderr)
        return 2
    gpy = graphify_python(repo_root)
    code = (
        "from pathlib import Path\n"
        "from graphify.transcribe import transcribe\n"
        f"p = transcribe(Path({str(audio_path)!r}), output_dir=Path({str(audio_path.parent)!r}))\n"
        "print('[kb-transcribe] transcript ->', p)\n"
    )
    print(f"  $ {gpy} -c '<graphify.transcribe.transcribe {audio_path.name}>'")
    return subprocess.run([gpy, "-c", code], cwd=repo_root, env=clean_env(), check=False).returncode
