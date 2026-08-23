# Copyright (c) 2026 Raymond Manaloto
r"""Lint ``.claude/workflows/*.js`` via transform-then-lint, never the source.

WHY THIS EXISTS, AND WHY IT IS NOT "RESTRUCTURE THE FILES". U8b0 rev1 pinned a
different mechanism — edit the three workflow files so a standalone parser
accepts their trailing top-level ``return`` directly. That mechanism is
IMPOSSIBLE, not merely hard: ``return`` outside a function body is an early
ECMAScript syntax error in every parse goal (Script or Module), independent of
whether ``export`` is present. Every Claude Code Workflow script begins with
``export const meta = {...}`` (a pure literal, required first statement) and
delivers its result via a bare top-level ``return`` that the RUNTIME wraps in
an async function at execution time — the wrapping function is never present
in the committed source. So the file must contain an unwrapped top-level
``return`` for the runtime to receive anything at all, and no legal rewrite of
the committed bytes can satisfy both "the runtime still gets the value" and "a
standalone parser sees zero errors". Confirmed empirically (four control-armed
biome probes: a bare top-level return fails identically with/without a leading
``export``; the same return nested in a real ``async`` IIFE parses clean
either way) and corroborated by four independent third-party workflow scripts
vendored elsewhere in this corpus, all sharing the identical shape. Full
evidence: ``.agent/kb/reports/agents/u8b0-workflow-lint-gate.md``. The
maintainer accepted the dissent and re-pinned the mechanism to this module,
2026-08-23.

THE MECHANISM. Never touch the committed file. Copy each workflow into a temp
directory, apply the exact transform the runtime itself effectively applies —
documented in the files' own header since before this gate existed
(``session-review.js:3-19``): strip the leading ``export`` from
``export const meta``, and wrap the remainder of the body in
``(async () => { ... })()`` so the trailing ``return`` lands inside a real
function. Then run biome against the COPY, and surface biome's real exit code.

ONE LINE, not an inserted one. The strip-and-wrap prefix replaces the existing
``export const meta = {`` line IN PLACE — same line, same line number — rather
than being inserted as a new line before it (which would shift every
subsequent line by one and make a reported line number point at the wrong
place in the real file). The closer, ``})()``, is APPENDED after the file's
last line, which shifts nothing that precedes it. Together these mean every
line number biome reports on the copy is the same line number in the real
file — verified in ``tests/test_workflow_lint.py`` by breaking a known line and
asserting the reported line matches it exactly, not "close to" it.

THE ``meta`` ARTIFACT, and why it gets its own config rather than a rewrite.
Stripping ``export`` turns an exported binding (exempt from unused-variable
analysis by definition — something else might import it) into a plain local
``const``. A workflow whose body never reads its own metadata by name — true
of ``kb-extract.js`` and ``kb-tool-review.js`` today, both of which reference
``meta`` exactly once, at its own declaration — then earns a
``lint/correctness/noUnusedVariables`` finding that cannot exist in the real
file: at runtime ``meta`` is genuinely read, by the harness, as the workflow's
name/description/phases; it is simply never referenced *from within the
script body*. That is the maintainer's own stated failure condition for the
"faithful stand-in" assumption (rev2 premise, assumption row): a finding that
appears on the copy and cannot exist in the real file. Per the constraint
carried over from rev1 ("disable it in biome's config with a written reason,
not at the callsite"), :data:`_BIOME_CONFIG` disables exactly that one rule,
for exactly this temp directory, with the reasoning above — every other rule,
INCLUDING parse errors, stays on. The alternative considered and rejected:
hand-locating each meta object's closing brace via a brace-depth scanner to
splice in a real reference. That is strictly more code and more fragile (a
brace inside a future string value in the meta block would misparse it) to
avoid a config line whose reason is written down beside it.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from kb_setup.result import Err, Rc, Result, exit_code, external_from_returncode

#: Where the workflow scripts live, relative to the repo root.
WORKFLOWS_DIR = Path(".claude/workflows")

#: The one line every workflow script must begin with (comments may precede
#: it — see the module docstring and `workflows.md`'s own canonical example).
#: Anchored to true column 0 of a real source line: a string or comment that
#: merely CONTAINS this text at a non-zero column never matches.
_META_LINE = re.compile(r"^export const meta\b")

#: Scoped to the gate's own temp copies, never to the committed source — see
#: the module docstring's "THE `meta` ARTIFACT" section for the full reason.
#: `.jsonc` (not `.json`) specifically so the reason can live beside the rule
#: it explains, rather than only in this docstring where a future reader of
#: the generated config would not see it.
_BIOME_CONFIG = """{
  // Scoped to kb_setup.workflow_lint's temp copies only — see that module's
  // docstring ("THE `meta` ARTIFACT"). Stripping `export` from `export const
  // meta` (so a standalone parser accepts the runtime-required trailing
  // top-level `return`) turns an exported, exemption-eligible binding into a
  // plain local `const`. A workflow whose body never reads its own metadata
  // by name then earns a noUnusedVariables finding that cannot exist in the
  // real file: at runtime `meta` is read by the harness itself. Every other
  // rule, including parse errors, stays on.
  "linter": {
    "rules": {
      "correctness": {
        "noUnusedVariables": "off"
      }
    }
  }
}
"""

#: Wall-clock bound on the biome invocation. biome lints these three files in
#: tens of milliseconds (measured); this exists only so a wedged process
#: cannot hang the gate — see `long-running-command-hangs.md`.
_TIMEOUT = 30


class ShapeError(Exception):
    """A workflow file no longer begins with `export const meta`.

    Raised by :func:`transform`, caught by :func:`run` and reported as a
    lint FINDING (the gate looked and found a real defect: the file no longer
    matches the Workflow runtime's required shape), never as an uncaught
    crash and never silently skipped.
    """


def transform(text: str, *, name: str) -> str:
    """Return `text` rewritten so a standalone JS parser accepts it.

    Replaces the leading `export const meta` line in place (same index, so no
    line number shifts) with an async-IIFE opener fused onto the same line,
    and appends the matching closer as a new final line (which shifts
    nothing that precedes it). See the module docstring for why this is safe
    and why the wrap cannot instead enclose only the tail of the file.

    Raises :class:`ShapeError` if no line begins with `export const meta` —
    fails loudly rather than silently emitting an unusable transform.
    """
    lines = text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        if _META_LINE.match(line):
            # "export const meta = {...}" -> "(async () => { const meta = {...}"
            lines[i] = "(async () => { " + line[len("export ") :]
            break
    else:
        msg = (
            f"{name}: no line begins with `export const meta` — the Workflow "
            "runtime's required shape (workflows.md's own canonical example; "
            "see this module's docstring). Cannot safely transform for "
            "standalone linting; this is a real defect in the file, not a "
            "gate malfunction."
        )
        raise ShapeError(msg)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append("})()\n")
    return "".join(lines)


def _display_path(name: str) -> str:
    """The path a human should see for `name`, resolved against the repo."""
    return str(WORKFLOWS_DIR / name)


def run(repo_root: Path) -> Result[int]:
    """Transform every workflow script into a temp copy, then lint the copies.

    Returns `External` — the result IS biome's own verdict over the transformed
    copies, per `result.py`'s guidance for "a command whose result is one
    subprocess's verdict" (a single `biome lint` invocation covers all files).
    """
    src_dir = repo_root / WORKFLOWS_DIR
    sources = sorted(src_dir.glob("*.js"))
    if not sources:
        return Err(
            f"no *.js files under {WORKFLOWS_DIR} — the gate did not run. "
            "This is NOT a pass: a walk that matched nothing never asked "
            "its question (probes-need-a-control-arm.md).",
            Rc.NOT_RUN,
        )

    with tempfile.TemporaryDirectory(prefix="kb-workflow-lint-") as tmp:
        tmp_path = Path(tmp)
        try:
            for src in sources:
                transformed = transform(src.read_text(encoding="utf-8"), name=src.name)
                (tmp_path / src.name).write_text(transformed, encoding="utf-8")
        except ShapeError as exc:
            return Err(str(exc), Rc.FINDINGS)

        # `_BIOME_CONFIG` is written INTO the temp dir and biome runs with
        # `cwd=tmp_path`, so biome resolves this config and no other. That is
        # deliberate — the config disables a rule that only fires because of the
        # transform — but it has a consequence a reader will not guess: biome
        # resolves config by walking UP from the linted file, so a `biome.json`
        # at the repo root would be silently ignored by this gate.
        #
        # There is none today (measured 2026-08-23). Rather than leave that as a
        # trap for whoever adds one, say so out loud: a root config appearing is
        # a real divergence between "the project's biome rules" and "the rules
        # this gate enforces", and it must not be discovered by wondering why an
        # edit had no effect. Refusing is the wrong shape (a root config is not a
        # defect), so this reports and continues. (Cold lane, 0e088a04, finding 4.)
        root_config = next(
            (p for p in (repo_root / name for name in ("biome.json", "biome.jsonc")) if p.exists()),
            None,
        )
        if root_config is not None:
            print(
                f"workflow-lint: NOTE — {root_config.name} exists at the repo root and this "
                "gate does NOT read it. The workflow scripts are linted as transformed copies "
                "in a temp dir under a self-contained config; rules added at the root do not "
                "reach them. Fold any rule you want enforced here into `_BIOME_CONFIG`."
            )
        (tmp_path / "biome.jsonc").write_text(_BIOME_CONFIG, encoding="utf-8")

        argv = ["biome", "lint", *(s.name for s in sources)]
        try:
            proc = subprocess.run(
                argv,
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                check=False,  # biome's own nonzero (findings/parse errors) IS the result we want
            )
        except FileNotFoundError:
            return Err(
                "biome not found on PATH. Pin/install it via mise "
                "(see mise.toml's [tools] table) before running this gate.",
                Rc.NOT_RUN,
            )
        except subprocess.TimeoutExpired:
            return Err(f"biome did not finish within {_TIMEOUT}s", Rc.NOT_RUN)
        except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as exc:
            return Err(f"biome could not run: {exc}", Rc.NOT_RUN)

        output = proc.stdout + proc.stderr
        # biome ran with cwd=tmp_path and bare filenames as argv, so its own
        # report already reads "session-review.js:1334:1" with no temp-dir
        # prefix to strip — just point each bare name at the real repo path,
        # so a reader (or an editor jump-to-file) resolves it against the
        # committed source, not the throwaway copy.
        for src in sources:
            output = output.replace(src.name, _display_path(src.name))
        if output.strip():
            print(output.rstrip())

        return external_from_returncode(
            proc.returncode, message=f"biome lint (transformed): {len(sources)} file(s)"
        )


def workflow_lint_main(repo_root: Path) -> int:
    """CLI entry point: `uv run kb-setup workflow-lint` (the hk step)."""
    result = run(repo_root)
    if isinstance(result, Err):
        print(f"workflow-lint: {result.message}")
    return exit_code(result)
