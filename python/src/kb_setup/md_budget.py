# Copyright (c) 2026 Raymond Manaloto
r"""Markdown instruction-file size budgets, BY LOAD CLASS — the shared engine.

``kb-setup md-budget`` (the ``md_size_budget`` hk step) is the ONE
implementation both this repo and ``ray-manaloto/dotfiles`` run, on the
``kb_setup.currency`` precedent: dotfiles consumes this package as a pinned
``uv`` git dependency rather than carrying a second copy that drifts. It
replaces the old ``claude_md_size_limit`` one-liner, which enforced a uniform
200-line/12000-byte cap on every ``CLAUDE.md``/``AGENTS.md``. That gate had
three defects, each established against primary sources in the dotfiles
research artifact ``docs/research/runs/research-20260715-md-size-limits/report.md``:

1. **The 12000-byte half was MISATTRIBUTED, not invented.** The figure is real
   — it is **Windsurf's**, not Anthropic's. Windsurf's own docs
   (<https://docs.windsurf.com/windsurf/cascade/memories>) state its Rules
   engine is "Limited to 12,000 characters per file", and that ``AGENTS.md`` is
   "processed by the same Rules engine". agnix enforces it as **AGM-003**
   (Category: agents-md, Tool: windsurf, Source type: vendor_docs). It appears
   nowhere in ANTHROPIC's docs — control-armed over the full corpus
   (``code.claude.com/docs/llms-full.txt``, 5,930,782 B, 2026-07-15):
   ``\b12,?000\b`` -> **0 hits**, vs 5 for MEMORY.md's cap and 12 for
   ``"200 lines"``. So captioning it "per Claude Code memory docs" was wrong
   about the SOURCE, not about the number. A CAUTIONARY NOTE ON THAT PROBE: it
   was bounded to Anthropic's corpus and answered truthfully within it; reading
   it as "undocumented anywhere" is the bound-dropping error
   ``probes-need-a-control-arm.md`` warns about, and it was made before agnix
   failed and surfaced Windsurf.
2. **It was class-blind.** It spent its whole budget on LAZY files while tens
   of KB of EAGER ``.claude/rules/*.md`` went ungoverned — anti-correlated
   with the context cost it existed to control.
3. **It counted disk bytes.** HTML comments are stripped before injection, so a
   CLAUDE.md's maintainer notes cost 0 bytes of context. Counting them measures
   what Claude never sees.

The one documented figure for author-written instruction files is:

    "Size: target under 200 lines per CLAUDE.md file. Longer files consume more
    context and reduce adherence."
    -- https://code.claude.com/docs/en/memory (Write effective instructions)

It is a SOFT guideline about a gradient, not a truncation point. The same page
states plainly: "CLAUDE.md files are loaded in full regardless of length,
though shorter files produce better adherence." Nothing here truncates.

Budgets differ BY LOAD CLASS because that is the docs' own cost model — a
limit's justification is *when* the bytes are spent:

- **eager**  root ``CLAUDE.md`` + its ``@import`` closure, and unscoped
  ``.claude/rules/*`` ("loaded at launch with the same priority as
  .claude/CLAUDE.md") -> the documented 200.
- **lazy**   nested ``CLAUDE.md``/``AGENTS.md`` ("included when Claude reads
  files in those subdirectories", and NOT re-injected after /compact) -> 400.
- **cond**   ``paths:``-scoped rules ("only load into context when Claude works
  with matching files") -> 400.
- **skill**  ``SKILL.md`` ("Keep under 500 lines"; loads on invocation only) ->
  500, plus the description cap below.

``SKILL_DESCRIPTION_MAX`` is the ONE hard-truncating limit a repo can actually
violate, and it fails silently: an over-long description is cut, so the
keywords Claude matches on vanish and the skill simply stops being discovered.

The byte ceilings are SELF-IMPOSED anti-gaming backstops (a line cap alone
admits 200 x 400-char lines), sized so they never bind before the documented
line limit does. They are OURS. Do not re-attribute them upstream — that
mistake is what this module exists to undo.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from kb_setup.result import Err, Ok, Rc, Result, exit_code

# --- Budgets -----------------------------------------------------------------

# The one documented figure ("target under 200 lines per CLAUDE.md file").
DOCUMENTED_LINE_TARGET = 200

# Relaxed ceiling for classes whose bytes are NOT spent at launch (lazy/cond).
# Self-imposed: no Anthropic figure governs these classes at all.
DEFERRED_LINE_LIMIT = 400

# "Keep under 500 lines" — https://code.claude.com/docs/en/skills
SKILL_LINE_LIMIT = 500

# HARD TRUNCATION. Raised 250 -> 1536 across v2.1.86..v2.1.105. An over-long
# description is silently cut, taking the matching keywords with it.
SKILL_DESCRIPTION_MAX = 1536

# Self-imposed byte backstops (~200 x 120 chars), NOT Anthropic figures.
EAGER_BYTE_BACKSTOP = 24_000
DEFERRED_BYTE_BACKSTOP = 32_000

# Vendored / third-party; not ours to budget. This is the UNION across the repos
# that consume this engine, which is why a prefix that matches nothing here is
# still listed — a shared default that silently omitted a consumer's carve-out
# would fail that repo, not this one. `plugins/` is dotfiles' vendored plugin
# cache; `.claude/skills/graphify/` is graphify's installer-generated skill in
# BOTH repos (SKILL.md is >700 lines, over the 500 guideline — regenerated by
# `graphify install`, never hand-edited, so budgeting it is meaningless). A
# consumer with a different carve-out passes its own via ``check(exclude=...)``.
DEFAULT_EXCLUDED_PREFIXES = (
    "plugins/",
    ".claude/skills/graphify/",
    # The codex lane's graphify stub — hand-written in `skill_refresh._CODEX_SKILL`
    # and regenerated wholesale, so it is generated output like its `.claude/`
    # namesake even though it is not the same bytes.
    ".agents/skills/graphify/",
)

# Docs: "maximum depth of four hops".
_MAX_IMPORT_DEPTH = 4

# Only CLAUDE.md is an ENTRY POINT: "Claude Code reads CLAUDE.md, not
# AGENTS.md. If your repository already uses AGENTS.md ... create a CLAUDE.md
# that imports it." So an AGENTS.md reaches context ONLY through its stub's
# @import, and is budgeted as a member of that closure — never standalone.
# Budgeting it twice would both double-count the eager total and blame the
# wrong file. This repo's AGENTS.md is a tracked SIBLING of CLAUDE.md (codex's
# minimum, not an @import stub), so no budget counts it here; dotfiles
# separately guarantees every AGENTS.md has its stub (`claude_agents_md_pairs`),
# which is what makes the closure-only treatment safe there: none is orphaned.
_ENTRY_RE = re.compile(r"(^|/)CLAUDE\.md$")
_RULE_RE = re.compile(r"^\.claude/rules/.*\.md$")
# BOTH skill trees. `.agents/skills/` is the tracked near-copy the non-Claude
# lanes read, and until 2026-08-17 it matched no budget class at all — so a copy
# could grow past every ceiling its `.claude/` twin is held to, silently, which
# is the same hole `skill_lint.DEFAULT_SKILL_GLOBS` closes for the other gate.
#
# One caveat on what this measures: the `skill` class's justification is "loaded
# on invocation/relevance only", which is Claude Code's mechanism. Whether the
# codex lane pays the same way is not documented here, so the ceiling is applied
# as a size discipline over a tracked instruction file rather than as a claim
# about that lane's loader.
_SKILL_RE = re.compile(r"^\.(claude|agents)/skills/.*/SKILL\.md$")

# An @import directive. Import parsing "skips Markdown code spans and fenced
# code blocks", so a backticked `@README` is a literal mention, not an import —
# hence the lookbehind, which also rejects an email's local part (`a@b.com`).
# The target may be a BARE filename (`@AGENTS.md` — dotfiles' root stub), so it
# must not require a `/`. Prose false positives are harmless: a target that
# does not resolve to a real file contributes nothing.
_IMPORT_RE = re.compile(r"(?<![`\w])@([A-Za-z0-9_./~-][^\s`]*)")


@dataclass
class Budget:
    """The ceiling for one load class."""

    max_lines: int
    max_bytes: int
    why: str


BUDGETS: dict[str, Budget] = {
    "eager_root": Budget(
        DOCUMENTED_LINE_TARGET,
        EAGER_BYTE_BACKSTOP,
        "loaded in full at launch, every session — the documented 200-line target",
    ),
    "rule_unscoped": Budget(
        DOCUMENTED_LINE_TARGET,
        EAGER_BYTE_BACKSTOP,
        "unscoped rule: loads at launch at the same priority as .claude/CLAUDE.md",
    ),
    "nested": Budget(
        DEFERRED_LINE_LIMIT,
        DEFERRED_BYTE_BACKSTOP,
        "lazy: loaded only when Claude reads files in that directory",
    ),
    "rule_scoped": Budget(
        DEFERRED_LINE_LIMIT,
        DEFERRED_BYTE_BACKSTOP,
        "paths:-scoped rule: loads only when Claude works with matching files",
    ),
    "skill": Budget(
        SKILL_LINE_LIMIT,
        DEFERRED_BYTE_BACKSTOP,
        "loads only on invocation/relevance — documented 500-line guideline",
    ),
}

# The classes whose bytes are spent at launch, every session.
EAGER_CLASSES = frozenset({"eager_root", "rule_unscoped"})


@dataclass
class Violation:
    """One budget breach."""

    path: str
    message: str


@dataclass
class Report:
    """The outcome of one budget sweep."""

    violations: list[Violation] = field(default_factory=list)
    eager_bytes: int = 0
    counted: int = 0


# --- Measurement -------------------------------------------------------------


def injected_text(raw: str, *, strip_comments: bool = True) -> str:
    """Strip what Claude never sees.

    "Block-level HTML comments (``<!-- maintainer notes -->``) **in CLAUDE.md
    files** are stripped before the content is injected into Claude's context.
    Use them to leave notes for human maintainers without spending context
    tokens on them." -- https://code.claude.com/docs/en/memory

    Counting them for CLAUDE.md would tax the exact practice the docs endorse
    as free.

    NOTE the scope of that sentence — it says "in CLAUDE.md files". Whether the
    same stripping applies to ``.claude/rules/*.md`` or ``SKILL.md`` is NOT
    documented, so callers for those classes pass ``strip_comments=False`` and
    pay full price. Assuming the discount where it is unproven would make the
    gate UNDER-count the eagerly-loaded class — the failure direction that
    matters. Being slightly strict there is the safe error.
    """
    return re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL) if strip_comments else raw


def measure(raw: str, *, strip_comments: bool = True) -> tuple[int, int]:
    """Return (lines, bytes) of the content that actually reaches context."""
    text = injected_text(raw, strip_comments=strip_comments).strip()
    if not text:
        return 0, 0
    return len(text.split("\n")), len(text.encode())


def has_paths_frontmatter(raw: str) -> bool:
    """True when the file opens with YAML frontmatter carrying a paths: key.

    Only real frontmatter counts — the document must OPEN with ``---``. A prose
    mention of "paths:" further down is not scoping, and treating it as such
    would silently hand a rule the relaxed budget it has not earned.
    """
    m = re.match(r"^---\n(.*?)\n---(\n|$)", raw, re.DOTALL)
    return bool(m) and re.search(r"^paths:", m.group(1), re.MULTILINE) is not None


def _frontmatter_field(front: str, field: str) -> str:
    d = re.search(
        rf"^{field}:\s*(.*?)(?=\n[A-Za-z_-]+:|\Z)",
        front,
        re.DOTALL | re.MULTILINE,
    )
    return d.group(1).strip() if d else ""


def skill_description(raw: str) -> str:
    """The text the 1,536-char cap actually applies to: description + `when_to_use`.

    BOTH fields, because the cap is on their COMBINED length — *"Appended to
    `description` in the skill listing and counts toward the 1,536-character
    cap"* (`code.claude.com/docs/en/skills.md`, Frontmatter reference). This
    measured `description` alone, so a skill splitting its text across the two
    fields would pass a gate that the harness would then truncate. No SKILL.md
    here uses `when_to_use` today, so the gate was not yet lying — it was simply
    unable to notice. (Cold lane round 2, P2; the rule file was corrected to the
    combined cap in the same branch, which is what made the gate disagree with
    its own documentation.)
    """
    m = re.match(r"^---\n(.*?)\n---(\n|$)", raw, re.DOTALL)
    if not m:
        return ""
    parts = [_frontmatter_field(m.group(1), f) for f in ("description", "when_to_use")]
    return " ".join(p for p in parts if p)


# --- Classification ----------------------------------------------------------


def classify(path: str, *, exclude: tuple[str, ...] = DEFAULT_EXCLUDED_PREFIXES) -> str | None:
    """Map a tracked path to its load class, or None when unbudgeted."""
    if path.startswith(exclude):
        return None
    if _SKILL_RE.match(path):
        return "skill"
    if _RULE_RE.match(path):
        return "rule_unscoped"  # refined by frontmatter at read time
    if not _ENTRY_RE.search(path):
        return None
    # The root CLAUDE.md and .claude/CLAUDE.md are "loaded in full at launch";
    # every other directory's stub is lazy ("included when Claude reads files
    # in those subdirectories").
    if "/" not in path or path.startswith(".claude/"):
        return "eager_root"
    return "nested"


@dataclass(frozen=True)
class Overlay:
    """A proposed-content view of the tree: overrides first, disk second.

    #698 needs to budget an edit BEFORE it happens, and the sweep must see the
    proposed bytes everywhere it would otherwise read disk. One object threaded
    through `check` -> `_size_of` -> `closure_size` -> `resolve_imports` is what
    makes that true; overriding only the top-level `read_text` was the second of
    the two holes the #700 design record found, because `closure_size` re-reads
    every `@import`ed member itself and would have counted stale bytes.

    `content` is keyed by repo-relative POSIX path — the same spelling
    `tracked_files` returns and `classify` expects — while the lookups take
    `Path`, because that is what the import walker carries.

    :data:`EMPTY` is the no-override case and is the default everywhere, so a
    plain sweep behaves exactly as it did before this class existed.
    """

    root: Path
    content: dict[str, str]

    def rel(self, path: Path) -> str | None:
        """``path`` as a repo-relative POSIX string, or ``None`` if outside."""
        try:
            return path.resolve().relative_to(self.root.resolve()).as_posix()
        except ValueError, OSError:
            return None

    def exists(self, path: Path) -> bool:
        """True when the overlay supplies ``path``, or it is a real file.

        The override arm is the FIRST of the two holes: a `Write` creating a new
        instruction file is untracked AND absent from disk, so `check`'s
        `not path.is_file()` skip made it invisible twice over — the guard would
        have waved through the one edit that can add a whole file to the budget.
        """
        rel = self.rel(path)
        if rel is not None and rel in self.content:
            return True
        return path.is_file()

    def read(self, path: Path) -> str:
        """The proposed bytes for ``path``, falling back to disk."""
        rel = self.rel(path)
        if rel is not None and rel in self.content:
            return self.content[rel]
        return path.read_text(errors="replace")


EMPTY = Overlay(Path(), {})
"""The no-override overlay. Every read falls through to disk."""


def resolve_imports(
    entry: Path, root: Path, depth: int = 0, overlay: Overlay | None = None
) -> list[Path]:
    """Return the transitive @import closure of ``entry``, including itself.

    Imports "are expanded and loaded into context at launch alongside the
    CLAUDE.md that references them", so the closure — not the file — is the
    unit that costs context. Budgeting per file would let any file evade its
    ceiling by splitting, which the docs explicitly call a non-reduction.
    """
    over = overlay if overlay is not None else EMPTY
    if depth > _MAX_IMPORT_DEPTH or not over.exists(entry):
        return []
    out = [entry]
    raw = injected_text(over.read(entry))
    # Fenced blocks are skipped by the real import parser; mirror that.
    raw = re.sub(r"```.*?```", "", raw, flags=re.DOTALL)
    for m in _IMPORT_RE.finditer(raw):
        target = m.group(1)
        if target.startswith("~"):
            continue  # a home-dir import is not this repo's to budget
        nxt = (entry.parent / target).resolve()
        try:
            nxt.relative_to(root)
        except ValueError:
            continue  # outside the repo
        if nxt not in out:
            out.extend(p for p in resolve_imports(nxt, root, depth + 1, over) if p not in out)
    return out


def closure_size(
    entry: Path, root: Path, overlay: Overlay | None = None
) -> tuple[int, int, list[Path]]:
    """Measure the (lines, bytes) of an entry's whole import closure.

    An import directive is REPLACED by the imported content, so the directive's
    own line must not be counted — otherwise dotfiles' root closure (CLAUDE.md's
    one `@AGENTS.md` line + AGENTS.md's 200) reads as 201 and a file sitting
    legitimately at the documented limit fails for a reason unrelated to size.
    """
    over = overlay if overlay is not None else EMPTY
    files = resolve_imports(entry, root, 0, over)
    lines = bytes_ = 0
    for f in files:
        raw = over.read(f)
        text = injected_text(raw)
        fenced = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        directives = len(_IMPORT_RE.findall(fenced))
        line_n, byte_n = measure(raw)
        lines += max(0, line_n - directives)
        bytes_ += byte_n
    return lines, bytes_, files


# --- The sweep ---------------------------------------------------------------


def tracked_files(root: Path) -> list[str]:
    """Every git-tracked path, for classification."""
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [f for f in out.stdout.split("\n") if f]


def _resolve_class(rel: str, raw: str, exclude: tuple[str, ...]) -> str | None:
    """Classify ``rel``, refining a rule by its frontmatter."""
    cls = classify(rel, exclude=exclude)
    if cls == "rule_unscoped" and has_paths_frontmatter(raw):
        return "rule_scoped"
    return cls


def _description_violation(rel: str, raw: str) -> Violation | None:
    """Catch the one HARD truncation: an over-long SKILL.md description."""
    desc = skill_description(raw)
    if len(desc) <= SKILL_DESCRIPTION_MAX:
        return None
    return Violation(
        rel,
        f"description + when_to_use is {len(desc)} chars (HARD cap {SKILL_DESCRIPTION_MAX}) "
        f"— the tail is TRUNCATED SILENTLY, taking the keywords Claude matches "
        f"on with it, so the skill stops being discovered",
    )


def _size_of(
    cls: str, path: Path, raw: str, root: Path, overlay: Overlay | None = None
) -> tuple[int, int, str]:
    """Return (lines, bytes, unit) for one file, by class."""
    if cls in ("eager_root", "nested"):
        lines, bytes_, files = closure_size(path, root, overlay)
        # Name the closure, not just the stub: a 1-line CLAUDE.md that imports
        # a 12KB AGENTS.md must not report "CLAUDE.md is too big".
        members = ", ".join(f.relative_to(root).as_posix() for f in files if f != path)
        return lines, bytes_, (f"closure incl. {members}" if members else "file")
    # Comment-stripping is documented for CLAUDE.md only; rules and skills pay
    # full price until proven otherwise (see injected_text).
    lines, bytes_ = measure(raw, strip_comments=False)
    return lines, bytes_, "file"


def check(
    root: Path,
    *,
    exclude: tuple[str, ...] = DEFAULT_EXCLUDED_PREFIXES,
    overrides: dict[str, str] | None = None,
) -> Report:
    """Budget every tracked instruction file by its load class.

    ``overrides`` maps a repo-relative POSIX path to the content it is ABOUT to
    have, so #698 can ask "would this edit breach a budget?" before the write
    lands. It is the same sweep either way — deliberately, because a second
    per-file checker would be free to disagree with the gate, and the whole
    point is that the hook and the gate cannot drift.

    An overridden path that git does not track is walked anyway. That is the
    `Write`-creates-a-new-file case, and without it the guard would be blind to
    the single edit that can add an entire file to the eager budget.
    """
    report = Report()
    overlay = Overlay(root, dict(overrides or {}))

    tracked = tracked_files(root)
    # An override for an already-tracked path must not be walked twice; one for
    # an untracked path is appended so a created file is still budgeted.
    extra = [rel for rel in overlay.content if rel not in set(tracked)]

    for rel in [*tracked, *extra]:
        path = root / rel
        if classify(rel, exclude=exclude) is None or not overlay.exists(path):
            continue
        raw = overlay.read(path)
        cls = _resolve_class(rel, raw, exclude)
        if cls is None:
            continue

        if cls == "skill" and (v := _description_violation(rel, raw)):
            report.violations.append(v)

        budget = BUDGETS[cls]
        lines, bytes_, unit = _size_of(cls, path, raw, root, overlay)

        report.counted += 1
        if cls in EAGER_CLASSES:
            report.eager_bytes += bytes_

        if lines > budget.max_lines:
            report.violations.append(
                Violation(
                    rel,
                    f"{lines} lines ({unit}) > {budget.max_lines} for class '{cls}' — {budget.why}",
                )
            )
        if bytes_ > budget.max_bytes:
            report.violations.append(
                Violation(
                    rel,
                    f"{bytes_} bytes ({unit}) > {budget.max_bytes} for class "
                    f"'{cls}' — self-imposed backstop, not an Anthropic figure",
                )
            )
    return report


def check_md_budget(
    root: Path, *, exclude: tuple[str, ...] = DEFAULT_EXCLUDED_PREFIXES
) -> Result[Report]:
    """The boundary (§2 R5): the budget report, and whether it is a finding.

    Returns rather than raises, and prints nothing — :func:`md_budget_main`
    renders. Same two-function split as ``check.check``/``check.main`` and
    ``lint_checks.check_no_lint_skip``, which is ``ruff``'s
    ``pub fn run(..) -> Result<ExitStatus>`` (``crates/ruff/src/lib.rs:128``).

    **Over-budget files are ``Ok``, not ``Err``.** This gate ran, it measured
    every tracked instruction file, and it found three of them too long — that
    is the gate succeeding. ``Err`` is "could not run".

    **A walk that matched nothing is ``Err(rc=Rc.NOT_RUN)``, not a pass** (#270,
    closed 2026-08-10). ``report.counted == 0`` means the gate never asked its
    question, which by ``probes-need-a-control-arm.md`` is a third state — not
    ``FINDINGS`` (we did not look) and not ``BAD_REQUEST`` (the request was
    fine). ``skill_lint`` already drew it that way; this module and ``distill``
    returned ``Rc.OK`` for the structurally identical case.

    It was left diverging through tranches 1-4 on purpose: a conversion's only
    regression arm is the pre-existing exit-code assertions, so changing an rc
    inside the commit that restructures the function deletes the evidence the
    restructure was safe. The divergence was pinned by a failing-on-purpose test
    instead, and this change is the deliberate edit to that assertion.

    **The blast radius, checked before landing rather than reasoned about.**
    This function IS the ``md_size_budget`` hk step, and dotfiles runs the same
    one via ``uv run --project python kb-setup md-budget`` (its ``hk.pkl``). It
    pins this package by SHA, so the new code reaches it only when that pin
    advances; and measured there on 2026-08-10, dotfiles counts **57**
    instruction files. ``counted == 0`` cannot arise in either repo under normal
    operation — and if it ever did, that is precisely the silent no-op this
    change exists to surface.
    """
    report = check(root, exclude=exclude)
    if report.counted == 0:
        return Err(
            "NO INSTRUCTION FILES MATCHED — the budget gate did not run. "
            "Check the walk before reading this as clean.",
            rc=Rc.NOT_RUN,
        )
    return Ok(report, rc=Rc.FINDINGS if report.violations else Rc.OK)


def md_budget_main(root: Path) -> int:
    """Entry point for ``kb-setup md-budget`` (and dotfiles' ``md-budget``).

    Kept returning ``int``: ``cli.py``, the ``md_size_budget`` hk step and this
    module's existing exit-code assertions are the regression arm proving the
    ``Result`` split changed no behaviour.
    """
    result = check_md_budget(root)
    # Narrowed on `Ok` rather than against `Err`: `Result` has a third variant
    # (`External`), so a negative test would leave a union ty rejects. This
    # boundary has no failure case today — the branch is the renderer honouring
    # the declared type, not a claim that one exists.
    if not isinstance(result, Ok):
        sys.stderr.write(f"md-budget: {result.message}\n")
        return exit_code(result)
    report = result.value
    for v in report.violations:
        sys.stderr.write(f"{v.path}: {v.message}\n")
    # The number that actually matters, surfaced every run: bytes paid at
    # launch in EVERY session, regardless of what the task touches.
    sys.stdout.write(
        f"md-budget: {report.counted} instruction files checked; "
        f"eager context ~{report.eager_bytes} bytes "
        f"(~{report.eager_bytes // 4} tokens) every session\n"
    )
    return exit_code(result)
