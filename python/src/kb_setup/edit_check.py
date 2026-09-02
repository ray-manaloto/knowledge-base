# Copyright (c) 2026 Raymond Manaloto
"""Give a codex lane the type diagnostics Claude gets for free.

WHY THIS EXISTS. Claude Code receives a ty diagnostic automatically after every
Edit-tool edit — measured 2026-09-02, #671. **Codex has no LSP client at all**
(#667: no LSP crate and zero protocol-method hits in the pinned `sources/codex/`
clone, against a control arm of 992 `mcp_servers` hits; `is:pr is:merged LSP`
returns 0 against a control of 174 for `mcp`). So a codex lane writes Python
with no type feedback whatsoever until a later `mise run lint` catches up.

Ray, 2026-09-02: *"we need to enable the same hooks for codex since the codex
lanes do most of the work"*. That is the whole justification — the gap is not a
nice-to-have, it is on the lane that writes most of this repo's code.

WHAT IT IS. A `PostToolUse` handler wired in `.codex/hooks.json` on matcher
`apply_patch`. It reads the patch, finds the Python files it touched, runs the
PROJECT's ty over them, and hands any diagnostics back to the lane as
`additionalContext`.

THE CONTRACT, read from the pinned codex docs rather than assumed — three
details, each of which would have produced a hook that silently does nothing:

1. **`apply_patch` sends `tool_input.command`, NOT a file path.**
   `hooks/index.md`: *"`Bash` and `apply_patch` use `tool_input.command`."* An
   earlier plan for this hook said codex "passes `${tool_input.file_path}`" — it
   does not, for this tool. The paths have to be parsed out of the patch body.
2. **"Plain text on `stdout` is ignored."** A hook that merely prints
   diagnostics achieves nothing. Feedback must be JSON carrying
   `hookSpecificOutput.additionalContext`, which codex adds as developer context.
3. **Output above roughly 2,500 tokens SPILLS** to
   `<temp_dir>/hook_outputs/<session_id>/<uuid>.txt`, and the model gets a
   head-and-tail preview instead. So this caps its own output rather than
   letting codex truncate it somewhere less useful.

WHICH ty, and why it is not the one Claude uses. Claude's ty comes from the
Astral plugin as `uvx ty@latest` — whatever shipped most recently, which Ray has
ruled acceptable for the editor ("always newest is fine"). This hook runs the
**project's** `.venv/bin/ty`, the binary the gates run. A lane's feedback
disagreeing with the gate that will judge it is worse than no feedback.

WHAT IT DELIBERATELY DOES NOT DO. It never blocks. `PostToolUse` supports
`decision: "block"` and `continue: false`, and both are wrong here: the edit has
already happened, and a type error is information the lane should act on, not a
reason to halt it. Codex's own docs draw the same line — *"Treat tool hooks as a
useful guardrail, not a complete enforcement boundary. Some specialized tool
paths can opt out of the default hook path."* A lane report claiming
"type-checked" on the strength of this hook would be overclaiming.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

#: The `apply_patch` envelope's path-bearing directives, read from the codex
#: source (`codex-rs/apply-patch/src/lib.rs`) rather than from memory.
#: `Delete File` is deliberately absent — a deleted file has nothing to check.
#: `Move to` names the DESTINATION, which is the path that now needs checking.
_PATCH_PATH = re.compile(
    r"^\*\*\*\s+(?:Add File|Update File|Move to):\s*(.+?)\s*$",
    re.MULTILINE,
)

#: Extensions ty type-checks. A patch that only touches markdown must cost
#: nothing — this hook runs after EVERY apply_patch in a codex lane.
_CHECKED_SUFFIXES = frozenset({".py", ".pyi"})

#: Wall-clock bound. ty is fast, but a hook that hangs stalls the lane's turn,
#: and `long-running-command-hangs.md` rule 2 forbids waiting blind.
_TIMEOUT_SECONDS = 60

#: Self-imposed cap, below codex's ~2,500-token spill threshold so the model
#: gets the diagnostics inline rather than a preview plus a temp-file path.
#: Characters, not tokens, because that is what we can count exactly.
_MAX_CONTEXT_CHARS = 6000


def _patched_python_files(command: str, repo_root: Path) -> list[Path]:
    """The `.py`/`.pyi` files this patch touches, that exist on disk now.

    Existence is checked HERE rather than in ty, because a `Move to:` source and
    a path from a patch that partly failed both name files ty would simply error
    on — and an error about a missing file, handed back as "type diagnostics",
    is the kind of noise that trains a lane to ignore this hook.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for raw in _PATCH_PATH.findall(command):
        candidate = Path(raw)
        if candidate.suffix not in _CHECKED_SUFFIXES:
            continue
        resolved = candidate if candidate.is_absolute() else repo_root / candidate
        if resolved in seen or not resolved.is_file():
            continue
        seen.add(resolved)
        found.append(resolved)
    return found


def _run_ty(ty: Path, paths: list[Path], repo_root: Path) -> str | None:
    """Return ty's report when it found something, else None. Never raises."""
    try:
        completed = subprocess.run(
            [str(ty), "check", *(str(p) for p in paths)],
            capture_output=True,
            text=True,
            timeout=_TIMEOUT_SECONDS,
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except OSError, subprocess.SubprocessError:
        return None
    if completed.returncode == 0:
        return None
    report = (completed.stdout or "") + (completed.stderr or "")
    return report.strip() or None


def _patch_command(payload: object) -> str:
    """The apply_patch body, or "" for any payload shape that has none."""
    if not isinstance(payload, dict):
        return ""
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    if not isinstance(command, str) or "*** " not in command:
        return ""
    return command


def _context_for(command: str, repo_root: Path) -> str | None:
    """Ty's verdict on this patch's Python files, as model-facing text."""
    paths = _patched_python_files(command, repo_root)
    if not paths:
        return None
    ty = repo_root / ".venv" / "bin" / "ty"
    if not ty.is_file():
        return None
    report = _run_ty(ty, paths, repo_root)
    if not report:
        return None
    if len(report) > _MAX_CONTEXT_CHARS:
        report = (
            report[:_MAX_CONTEXT_CHARS]
            + "\n… truncated; run `mise run kb-check -- <paths>` for the rest."
        )
    return (
        "ty reported type errors in the file(s) this patch touched. Codex has no "
        "language server, so this is the only type feedback this lane gets — the "
        "same diagnostics a Claude session receives automatically after an edit.\n\n"
        f"{report}"
    )


def run(repo_root: Path) -> int:
    """Codex `PostToolUse` entry. Reads the hook payload on stdin.

    Always exits 0. This hook exists to ADD information; a failure inside it
    must never cost the lane its turn, and codex treats a non-zero exit plus
    stderr as blocking feedback — which is exactly what this must not do.
    """
    try:
        command = _patch_command(json.load(sys.stdin))
        context = _context_for(command, repo_root) if command else None
    except Exception:
        return 0
    if context:
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": context,
                }
            },
            sys.stdout,
        )
    return 0
