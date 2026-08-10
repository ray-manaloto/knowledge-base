# Copyright (c) 2026 Raymond Manaloto
"""`kb-remember` — record a Q&A outcome to work memory, with its lesson intact.

WHY THIS MODULE EXISTS, measured rather than supposed. `kb-remember` was a bare
seam onto `graphify save-result`. That command accepts `--correction TEXT`, and
`graphify reflect` renders exactly that field into `reflections/LESSONS.md`:

    out.append(f'- "{c["question"]}" → {c["correction"]}')   # reflect.py

Nothing on this side ever passed it. The mise task's own description listed
`--question / --answer / --nodes / --outcome` and stopped there, so every
session recorded `--outcome corrected` with no text, and the aggregate rendered
the question followed by an empty arrow.

**The loss, control-armed.** Of 32 memories carrying `outcome: "corrected"`,
**11** have a `correction:` field and **21** do not — and the split is exactly
the split in `LESSONS.md`: 32 unique correction entries, 21 of them empty. The
arm is the 11 that render fine under the same renderer, so the empty 21 are a
writer defect and not a rendering one.

The lessons themselves were never lost — they are in each memory's `## Answer`
body, on disk, in git. What was lost is the one artifact a future session
actually reads for orientation. That is R9's own shape: the record survives, the
finding is buried, and the tool exits 0.

**Why a module and not a longer task description.** This repo has measured what
prose-only guidance is worth: a directive enforced by a DENY went 62 → 0
violations, while the warning-only one it replaced was complied with 0 times out
of 19 (`.claude/rules/mise-tasks-only.md`). A `--correction` you have to
remember is the second kind. Here it is a refusal: `--outcome corrected` without
a stated lesson is `BAD_REQUEST`, which is the same rule `Err` already enforces
one layer down — *an unexplained outcome is the defect R9 names*.

**`--correction-file` exists here and not upstream, deliberately.** Prose passed
inline to a CLI through a shell has executed its own backticks into this corpus
before. Every argument here reaches `graphify` through `subprocess.run` with an
argv **list**, which spawns no shell, so a correction containing backticks is
safe either way — but the file form is what makes a multi-line lesson writable
at all, and it is the form the skills should reach for.
"""

from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from kb_setup.graphify_env import clean_env, graphify_exe
from kb_setup.result import Err, External, Ok, Rc, Result, exit_code, external_from_returncode

if TYPE_CHECKING:
    from collections.abc import Sequence

#: The `--outcome` value that obliges a lesson. `useful` and `dead_end` do not:
#: a useful answer's lesson IS its answer, and a dead end's lesson is its
#: question. Only `corrected` names a *replacement* belief, and that is the one
#: `reflect` renders into a field nothing was filling.
_OBLIGES_LESSON = "corrected"

_OUTCOMES = ("useful", "dead_end", _OBLIGES_LESSON)

#: How many lossy memories the audit names before truncating. The point of the
#: message is the CLASS and its size; the full list is one `--json` away.
_MAX_SHOWN = 12


@dataclass(frozen=True, slots=True)
class RememberRequest:
    """A validated `save-result` invocation, ready to hand to graphify."""

    question: str
    query_type: str
    outcome: str | None
    answer: str | None = None
    correction: str | None = None
    nodes: tuple[str, ...] = ()
    memory_dir: str | None = None
    """Where the memory lands. Passed through to `save-result`, which owns the
    default (`graphify-out/memory`). Exposed so the write path can be exercised
    against a scratch directory — a gate proven only in the refusing direction
    is half a gate, and the passing half must not have to write to the corpus."""

    def argv(self, exe: str) -> list[str]:
        """The `graphify save-result` argv this request becomes.

        A list, never a string: `subprocess.run` with a list spawns no shell, so
        a lesson containing backticks is recorded rather than executed.
        """
        cmd = [exe, "save-result", "--question", self.question, "--type", self.query_type]
        if self.answer is not None:
            cmd += ["--answer", self.answer]
        if self.outcome is not None:
            cmd += ["--outcome", self.outcome]
        if self.correction is not None:
            cmd += ["--correction", self.correction]
        if self.memory_dir is not None:
            cmd += ["--memory-dir", self.memory_dir]
        if self.nodes:
            cmd += ["--nodes", *self.nodes]
        return cmd


@dataclass(frozen=True, slots=True)
class LossyMemory:
    """One memory that records a correction without stating it."""

    path: Path
    question: str


@dataclass(frozen=True, slots=True)
class LessonAudit:
    """What `--audit` found across the work-memory directory."""

    scanned: int
    corrected: int
    lossy: list[LossyMemory] = field(default_factory=list)

    @property
    def intact(self) -> int:
        """Corrections that DO carry their lesson — the audit's control arm."""
        return self.corrected - len(self.lossy)


def _text_of(inline: str | None, path_str: str | None, *, flag: str) -> str | Err | None:
    """Resolve an inline/`--*-file` pair to text, or an `Err` naming the conflict."""
    if inline is not None and path_str is not None:
        return Err(f"pass --{flag} or --{flag}-file, not both", rc=Rc.BAD_REQUEST)
    if path_str is None:
        return inline
    path = Path(path_str)
    if not path.is_file():
        return Err(f"--{flag}-file: no such file: {path}", rc=Rc.BAD_REQUEST)
    return path.read_text(encoding="utf-8")


def _validate_flags(opts: argparse.Namespace, unknown: list[str]) -> Err | None:
    """The flag-shape checks that do not need any file read. `None` when clean."""
    if unknown:
        return Err(f"unknown argument(s): {' '.join(unknown)}", rc=Rc.BAD_REQUEST)
    if not opts.question or not opts.question.strip():
        return Err("--question is required and must not be empty", rc=Rc.BAD_REQUEST)
    if opts.outcome is not None and opts.outcome not in _OUTCOMES:
        return Err(
            f"--outcome must be one of {', '.join(_OUTCOMES)} (got {opts.outcome!r})",
            rc=Rc.BAD_REQUEST,
        )
    return None


def check_remember(argv: Sequence[str]) -> Result[RememberRequest]:
    """Validate a `kb-remember` request. Returns, never raises, PRINTS NOTHING.

    The one rule this adds over `graphify save-result`: an outcome of
    `corrected` must state what the correction IS. Recording that a belief was
    wrong without recording the replacement produces a `LESSONS.md` line that
    names a question and answers nothing.
    """
    parser = argparse.ArgumentParser(prog="kb-remember", add_help=False)
    parser.add_argument("--question")
    parser.add_argument("--answer")
    parser.add_argument("--answer-file", dest="answer_file")
    parser.add_argument("--correction")
    parser.add_argument("--correction-file", dest="correction_file")
    parser.add_argument("--type", dest="query_type", default="query")
    parser.add_argument("--outcome", default=None)
    parser.add_argument("--nodes", nargs="*", default=[])
    parser.add_argument("--memory-dir", dest="memory_dir", default=None)
    opts, unknown = parser.parse_known_args(list(argv))

    bad = _validate_flags(opts, unknown)
    if bad is not None:
        return bad

    answer = _text_of(opts.answer, opts.answer_file, flag="answer")
    if isinstance(answer, Err):
        return answer
    correction = _text_of(opts.correction, opts.correction_file, flag="correction")
    if isinstance(correction, Err):
        return correction

    if opts.outcome == _OBLIGES_LESSON and not (correction or "").strip():
        return Err(
            "--outcome corrected requires --correction or --correction-file: "
            "state the belief that REPLACES the wrong one. Without it "
            "reflections/LESSONS.md renders this question with an empty lesson, "
            "which is the only artifact a future session reads for orientation.",
            rc=Rc.BAD_REQUEST,
        )

    return Ok(
        RememberRequest(
            question=opts.question,
            query_type=opts.query_type,
            outcome=opts.outcome,
            answer=answer,
            correction=correction,
            nodes=tuple(opts.nodes),
            memory_dir=opts.memory_dir,
        )
    )


def _frontmatter(text: str) -> dict[str, str]:
    """Parse the simple `---` frontmatter `save-result` writes (JSON-scalar values)."""
    if not text.startswith("---"):
        return {}
    _, _, rest = text.partition("\n")
    body, sep, _ = rest.partition("\n---")
    if not sep:
        return {}
    out: dict[str, str] = {}
    for line in body.splitlines():
        key, colon, value = line.partition(":")
        if colon:
            out[key.strip()] = value.strip().strip('"')
    return out


def check_memory_lessons(memory_dir: Path) -> Result[LessonAudit]:
    """Find memories that record a correction without stating it.

    Returns, never raises, PRINTS NOTHING.

    An empty or absent memory directory is `NOT_RUN`, not a clean bill: a walk
    that matched nothing never asked the question, and reporting that as `OK` is
    the exact divergence `probes-need-a-control-arm.md` exists to forbid.
    """
    if not memory_dir.is_dir():
        return Err(f"no work-memory directory at {memory_dir}", rc=Rc.NOT_RUN)

    files = sorted(memory_dir.glob("*.md"))
    if not files:
        return Err(f"no memories under {memory_dir} — nothing was audited", rc=Rc.NOT_RUN)

    corrected = 0
    lossy: list[LossyMemory] = []
    for path in files:
        meta = _frontmatter(path.read_text(encoding="utf-8"))
        if meta.get("outcome") != _OBLIGES_LESSON:
            continue
        corrected += 1
        if not meta.get("correction", "").strip():
            lossy.append(LossyMemory(path=path, question=meta.get("question", "")))

    audit = LessonAudit(scanned=len(files), corrected=corrected, lossy=lossy)
    return Ok(audit, rc=Rc.FINDINGS if lossy else Rc.OK)


def render_audit(audit: LessonAudit) -> str:
    """The operator-facing audit report."""
    lines = [
        (
            f"[remember] audited {audit.scanned} memories: "
            f"{audit.corrected} corrections, {audit.intact} with a lesson, "
            f"{len(audit.lossy)} WITHOUT"
        )
    ]
    if not audit.lossy:
        lines.append("[remember] every recorded correction states its lesson.")
        return "\n".join(lines)
    lines.append(
        "[remember] these render in reflections/LESSONS.md as a question with "
        "an empty lesson; the text is in each file's `## Answer` body:"
    )
    lines.extend(f"  - {item.path.name}: {item.question[:90]}" for item in audit.lossy[:_MAX_SHOWN])
    if len(audit.lossy) > _MAX_SHOWN:
        lines.append(f"  … and {len(audit.lossy) - _MAX_SHOWN} more")
    return "\n".join(lines)


def audit_main(repo_root: Path) -> int:
    """Render the work-memory lesson audit, then convert."""
    result = check_memory_lessons(repo_root / "graphify-out" / "memory")
    if isinstance(result, Ok):
        print(render_audit(result.value))
    else:
        print(f"[remember] {result.message}")
    return exit_code(result)


def main(repo_root: Path, argv: Sequence[str] = ()) -> int:
    """Record one Q&A outcome to work memory. Renders, then converts."""
    args = list(argv)
    if "--audit" in args:
        return audit_main(repo_root)

    result = check_remember(args)
    if isinstance(result, Err):
        print(f"[remember] refusing — {result.message}")
        return exit_code(result)
    if isinstance(result, External):  # pragma: no cover - check_remember never returns one
        return exit_code(result)

    request = result.value
    completed = subprocess.run(
        request.argv(graphify_exe(repo_root)),
        cwd=repo_root,
        env=clean_env(),
        check=False,
    )
    return exit_code(external_from_returncode(completed.returncode))
