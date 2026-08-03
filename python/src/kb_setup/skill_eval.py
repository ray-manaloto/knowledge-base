"""Score this repo's skills with `plugin-eval`'s deterministic static layer.

The answer to #124 — *"how do we MEASURE whether a skill works?"*. Before this,
we ran project skills with no way to tell a good one from a placebo: a prior
round scored `goal-engineering` at 92% against a 92% baseline (delta 0.00) and
had to conclude its value was procedural. A number that moves is the difference
between improving a skill and redecorating it.

**Layer 1 only, deliberately.** `plugin-eval` ships three layers — static (pure
python, no LLM, <2s), an LLM judge (~30s, 4 calls), and Monte Carlo (50-100
simulated runs). Only the static layer is wired here, because only it is free,
deterministic, and therefore comparable across runs. The judge and Monte Carlo
layers are reachable by hand (`--depth standard` / `certify`) when a specific
question needs them; they are not what a repeatable baseline is made of.

**ADVISORY on its FINDINGS — a score never fails a gate**, same posture as
`kb-currency` and `kb-goal-check`. Any floor picked before a baseline existed
would be invented rather than measured; `zero-skip-policy.md` would then force
sessions to chase a number nobody validated. Ray's call, 2026-08-03: *"advisory
now, ratchet later"*. Read the table, not the rc.

Advisory governs findings, **not a malformed request**: a skill name that
matches nothing exits **2**, exactly as `currency.run` does for an unknown
`--tool` ("a silent 0 would hide a typo"). Measured before the fix:
`mise run kb-skill-score -- clear-prpe` printed *"no skill directories under
.claude/skills"* and exited 0 while **7** skills existed — a typo rendered as an
empty corpus, in the one module whose docstring claims "could not measure" and
"measured badly" are different answers.

**The baseline is committed, and comparison is the tool's job.** `--write`
records `docs/skills/baseline.json` + a rendered `README.md`; every later run
prints a Δ column against it. An absolute score has no floor behind it, so a
delta is the only reading that means anything — and a delta an agent has to
assemble by hand from two transcripts is one nobody will compute. A baseline
recorded by a DIFFERENT scorer shows no delta at all rather than a misleading
one.

**It reports WHICH copy of plugin-eval scored you, and refuses to imply
otherwise.** `plugin-eval` reaches this host by two independent routes — the
Claude Code marketplace checkout under `~/.claude/plugins`, and this repo's own
pinned clone of `wshobson/agents` — and they can be different versions. A score
is only comparable to another score from the same scorer, so the provenance line
is part of the result, not decoration. When no copy is reachable the run reports
*NOT VERIFIABLE HERE* and scores nothing; it never prints a zero, because
"could not measure" and "measured badly" are different answers
(`probes-need-a-control-arm.md`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

#: Where `plugin-eval` can legitimately be found, best-provenance first.
#:
#: The marketplace checkout comes first because that is how Ray chose to install
#: it (2026-08-03) and it is the copy whose `/eval` slash command a session would
#: reach — scoring with a different build than the one the model uses would make
#: the two disagree for no visible reason. The pinned clone is the fallback that
#: makes a fresh checkout scoreable at all: `~/.claude` is not this repo's to
#: populate, so on a machine that never installed the plugin the manifest clone
#: is the only copy that exists.
_PLUGIN_ROOTS: tuple[tuple[str, str], ...] = (
    ("marketplace", "~/.claude/plugins/marketplaces/claude-code-workflows/plugins/plugin-eval"),
    ("pinned-clone", "sources/agents/plugins/plugin-eval"),
)

#: Skill directories are scored as a set so the table is comparable run to run.
_SKILLS_DIR = ".claude/skills"

#: The committed baseline every later run is read against, and the rendered
#: table beside it. `docs/currency/` is the shape being copied: a tracked run log
#: nobody has to reconstruct from a transcript.
_BASELINE_JSON = "docs/skills/baseline.json"
_BASELINE_MD = "docs/skills/README.md"

#: Every flag `main` accepts. Anything else prefixed `-` is a malformed request,
#: not a skill name — see `main`.
_FLAGS = frozenset({"--write"})

_SCORE_TIMEOUT_S = 120.0

#: `version = "0.1.0"` out of a pyproject, without a TOML parse of a file we do
#: not own. Anchored to the line start so a dependency's version cannot match.
_VERSION_RE = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class Scorer:
    """The `plugin-eval` copy that actually ran, and where it came from."""

    root: Path
    origin: str
    version: str

    def key(self) -> str:
        """The COMPARABILITY key — what two runs must share to be diffable.

        Deliberately path-free. `root` is an absolute path under `~`, so keying
        on it would (a) commit one developer's home directory into a tracked
        artifact and (b) make every Δ vanish on any other machine, even when the
        identical plugin-eval build scored both. Version and origin are the facts
        that decide comparability; where the checkout happens to live is not.
        """
        return f"plugin-eval {self.version or '(version unknown)'} [{self.origin}]"

    def label(self) -> str:
        """The key plus the checkout that produced it — console provenance."""
        return f"{self.key()} at {self.root}"


@dataclass(frozen=True)
class SkillScore:
    """One skill's static score, or the reason it has none."""

    name: str
    score: float | None
    anti_patterns: tuple[str, ...] = ()
    #: `composite.anti_pattern_penalty` — a MULTIPLIER on the composite, not a
    #: dimension. Carried because without it the score is unexplainable from the
    #: report: an edit to `clear-prep` improved every reported dimension
    #: (token_efficiency 0.988→0.989, ecosystem_coherence 0.990→1.000) and the
    #: composite still fell 66.1→62.8, purely because a x0.95 penalty appeared.
    #: A reader shown only dimensions would conclude the tool was broken.
    penalty: float = 1.0
    weakest: str = ""
    error: str = ""
    vendored: bool = False


def resolve_scorer(repo_root: Path) -> Scorer | None:
    """First reachable `plugin-eval` checkout, or None when there is none.

    Returning None is a real answer and is rendered as *NOT VERIFIABLE HERE*, not
    as a score of zero. A missing scorer says nothing whatsoever about skill
    quality, and a table that filled the gap with 0.0 would read as a catastrophic
    regression on any machine that simply had not installed the plugin.
    """
    for origin, raw in _PLUGIN_ROOTS:
        root = Path(raw).expanduser() if raw.startswith("~") else repo_root / raw
        if (root / "pyproject.toml").is_file():
            return Scorer(root=root, origin=origin, version=_version_of(root))
    return None


def vendored_names(repo_root: Path) -> frozenset[str]:
    """Skill directory names a tool's own installer regenerates, from `currency.toml`.

    `graphify/` is installer-generated (`graphify install --project`), >700 lines,
    and never hand-edited — `md-size-budgets.md` exempts it from the markdown
    budget for exactly that reason. It is still SCORED (a vendored skill we ship
    is one we are judged by), but flagged, so nobody spends a round "fixing" a
    file the next `kb-currency` bump overwrites.

    Read from config rather than hardcoded, because `currency/config.py` already
    says which side of that line this belongs on: *"Declared here rather than
    hardcoded in `currency.skill` so this stays a config-not-code engine."* A
    second tool that ships a project-scoped skill then needs no edit here.

    A missing or malformed `currency.toml` yields an empty set — the flag is
    simply absent. It is a cosmetic table cell, not a score, and `config.load`
    RAISES on a malformed table: letting that escape would kill an advisory
    scoring run over a defect in a different subsystem. `kb-currency-check` is
    where a broken config is a finding; here it is only ever a missing note, and
    it says so on stderr rather than vanishing.
    """
    from kb_setup.currency import config

    try:
        specs = config.load(repo_root)
    except (OSError, ValueError, TypeError) as exc:
        print(f"[skill-score] vendored flags unavailable — currency.toml: {exc}", file=sys.stderr)
        return frozenset()
    return frozenset(Path(spec.skill_dir).name for spec in specs if spec.skill_dir)


def _version_of(root: Path) -> str:
    """`plugin-eval`'s own declared version, or "" when it cannot be read."""
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _VERSION_RE.search(text)
    return match.group(1) if match else ""


def skill_dirs(repo_root: Path, names: list[str] | None = None) -> tuple[list[Path], list[str]]:
    """`(directories to score, requested names that resolve to no skill)`.

    A directory only counts when it holds a `SKILL.md`: `.claude/skills/` also
    accumulates `references/` and `scripts/` subtrees belonging to a skill, and
    handing one of those to `plugin-eval` would score a fragment as if it were a
    skill.

    The unresolved names are returned rather than dropped, and that is the whole
    point of the second element. Filtering them out silently made a typo produce
    the same output as an empty corpus — `-- clear-prpe` reported *"no skill
    directories under .claude/skills"* with 7 present. Two answers that differ
    ("you asked for something that is not here" vs "there is nothing here") must
    not share one rendering.
    """
    base = repo_root / _SKILLS_DIR
    if names:
        wanted = [base / n for n in names]
    else:
        wanted = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    found = [p for p in wanted if (p / "SKILL.md").is_file()]
    resolved = {p.name for p in found}
    return found, [n for n in names or () if n not in resolved]


def score_one(scorer: Scorer, skill_dir: Path, *, vendored: bool = False) -> SkillScore:
    """Run the static layer over one skill directory."""
    name = skill_dir.name
    proc = subprocess.run(
        [
            "uv",
            "run",
            "--project",
            str(scorer.root),
            "plugin-eval",
            "score",
            str(skill_dir),
            "--depth",
            "quick",
            "--output",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=_SCORE_TIMEOUT_S,
        # `uv` picks up an ambient VIRTUAL_ENV and warns that it does not match
        # the project it was asked for. Harmless, but it lands on stderr of every
        # single skill and buries a real failure under N copies of a non-problem.
        env={k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"},
    )
    if proc.returncode != 0:
        return SkillScore(name=name, score=None, error=_first_line(proc.stderr), vendored=vendored)
    return _parse(name, proc.stdout, vendored=vendored)


def _parse(name: str, stdout: str, *, vendored: bool) -> SkillScore:
    """Read the overall score out of `plugin-eval --output json`.

    Tolerant of leading non-JSON: `uv` may prepend build/install chatter on a
    cold cache, and a hard `json.loads(stdout)` would then report a parse error
    for a run that succeeded.
    """
    start = stdout.find("{")
    if start < 0:
        return SkillScore(name=name, score=None, error="no JSON in output", vendored=vendored)
    try:
        data = json.loads(stdout[start:])
    except (json.JSONDecodeError, ValueError) as exc:
        return SkillScore(name=name, score=None, error=f"unparsable: {exc}", vendored=vendored)
    if not isinstance(data, dict):
        return SkillScore(name=name, score=None, error="JSON is not an object", vendored=vendored)
    composite = data.get("composite")
    raw = composite.get("score") if isinstance(composite, dict) else None
    if not isinstance(raw, (int, float)):
        return SkillScore(name=name, score=None, error="no composite score", vendored=vendored)
    penalty = composite.get("anti_pattern_penalty") if isinstance(composite, dict) else None
    return SkillScore(
        name=name,
        score=float(raw),
        anti_patterns=_anti_patterns(data),
        penalty=float(penalty) if isinstance(penalty, (int, float)) else 1.0,
        weakest=_weakest(data),
        vendored=vendored,
    )


def _anti_patterns(data: Mapping[str, object]) -> tuple[str, ...]:
    """Anti-pattern names, gathered across every layer that ran.

    They live per-layer (`layers[].anti_patterns`) rather than at the top level,
    so a top-level lookup silently returns none — a count of 0 that means "not
    where I looked", not "none found". Exactly the shape of false-green this
    repo's probe rule exists to stop, which is why it is read per-layer here.

    **`flag` is the real key, and getting it wrong reproduced the same false
    green one level down.** plugin-eval 0.1.0 emits
    `{"flag": "DEAD_CROSS_REF", "description": ..., "severity": 0.05}`; this
    function read `name`/`type`/`pattern`, matched none of them, and reported
    **0 anti-patterns for all 7 of this repo's skills when 5 had one** — a
    claim that reached the committed baseline, a commit message and a session
    handoff before anyone questioned it. The unit test passed throughout because
    its fixture used `name`, so the test and the code shared one wrong
    assumption and agreed with each other (`probes-need-a-control-arm.md`; the
    fixture-shaped-test failure mode).

    Measured, not guessed: the key list below is ordered by what plugin-eval
    actually emits, with the others kept as tolerant fallbacks.
    """
    layers = data.get("layers")
    if not isinstance(layers, list):
        return ()
    names: list[str] = []
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        found = layer.get("anti_patterns")
        if not isinstance(found, list):
            continue
        for item in found:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, dict):
                label = (
                    item.get("flag") or item.get("name") or item.get("type") or item.get("pattern")
                )
                if isinstance(label, str):
                    names.append(label)
    return tuple(names)


def _weakest(data: Mapping[str, object]) -> str:
    """The lowest-scoring WEIGHTED dimension — where a point is actually cheapest.

    Weighted, not raw: `output_quality` scores 0.0 on every static-only run
    because its evidence comes from the LLM-judge layer we deliberately do not
    run, so a raw minimum would name the same untouchable dimension for every
    skill forever and point every reader at work that cannot be done.
    """
    composite = data.get("composite")
    dims = composite.get("dimensions") if isinstance(composite, dict) else None
    if not isinstance(dims, list):
        return ""
    reachable: list[tuple[float, float, str]] = []
    for entry in dims:
        if not isinstance(entry, dict):
            continue
        score, weight = entry.get("score"), entry.get("weight")
        if not isinstance(score, (int, float)) or score <= 0.0:
            continue
        reachable.append(
            (
                float(score),
                float(weight) if isinstance(weight, (int, float)) else 0.0,
                str(entry.get("name", "?")),
            )
        )
    if not reachable:
        return ""
    # Ties break toward the HEAVIER dimension: two dimensions equally weak are
    # not equally worth fixing.
    score, weight, name = min(reachable, key=lambda t: (t[0], -t[1]))
    return f"{name} {score:.2f} (w{weight:.2f})"


def _first_line(text: str) -> str:
    """The first non-empty line of a failure, for a one-row table cell."""
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:160]
    return "failed with no output"


@dataclass(frozen=True)
class Baseline:
    """The committed scores a run is read against, and who measured them."""

    scorer: str
    scores: Mapping[str, float]

    def delta(self, result: SkillScore, scorer: Scorer) -> str:
        """`+1.4` / `-0.5` / `—`, or `—` when the two runs are not comparable.

        A score is only comparable to another score from the SAME scorer — the
        provenance line exists for that reason, and a delta that quietly spans
        two `plugin-eval` builds would be the exact false-precision this module
        refuses everywhere else. Different scorer, no number.
        """
        if self.scorer != scorer.key() or result.score is None:
            return "—"
        before = self.scores.get(result.name)
        if before is None:
            return "new"
        # Rounded first. The baseline stores 1dp while a live score carries full
        # precision, so an unchanged skill differenced raw renders as `-0.0` —
        # a regression that did not happen, on a column whose whole job is to
        # show movement.
        moved = round(round(result.score, 1) - before, 1)
        return "0.0" if moved == 0 else f"{moved:+.1f}"


def load_baseline(repo_root: Path) -> Baseline | None:
    """The committed baseline, or None when there is none / it is unreadable.

    Unreadable is deliberately the same answer as absent: the fallback is "no Δ
    column", which under-claims rather than over-claims. There is no state in
    which a corrupt baseline produces a delta.
    """
    try:
        data = json.loads((repo_root / _BASELINE_JSON).read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError, ValueError:
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get("scores")
    scores = {
        str(k): float(v)
        for k, v in (raw.items() if isinstance(raw, dict) else ())
        if isinstance(v, (int, float))
    }
    return Baseline(scorer=str(data.get("scorer", "")), scores=scores)


def write_baseline(
    repo_root: Path,
    scorer: Scorer,
    results: list[SkillScore],
    *,
    previous: Baseline | None = None,
) -> Path:
    """Record this run as the committed baseline; returns the JSON path.

    **Raises `ValueError` unless every result scored.** Writing a baseline from a
    run where a skill failed would DELETE that skill's last known score: the
    payload is built from this run's results, so a skill with no number simply
    stops being a key, and the next successful run reports it as `new` rather
    than showing the delta it actually moved. One `subprocess.TimeoutExpired` —
    the case the timeout handling exists for — is enough to trigger it, which is
    what makes silence the wrong answer.

    Refusing rather than carrying the old value forward is the same rule
    `--write` already applies to a name-filtered run: a baseline is the FULL
    table or it is a trap. Carrying forward would put a number in the file that
    this run did not measure, and nothing downstream could tell the two apart.

    The rendered `README.md` carries the Δ against the baseline being REPLACED,
    which is the only moment that movement is knowable — the old numbers are gone
    the instant the JSON is rewritten.
    """
    unscored = [r.name for r in results if r.score is None]
    if unscored:
        # Checked HERE, at the point of use, rather than only in `main`: this is
        # the function that destroys the old file, so it is the function that has
        # to refuse.
        raise ValueError(
            f"refusing to write a baseline: {', '.join(sorted(unscored))} did not score, "
            f"and writing would delete the last score they had"
        )
    path = repo_root / _BASELINE_JSON
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = _render(
        scorer,
        results,
        baseline=previous,
        no_baseline_note="First baseline — there were no prior scores to compare against.",
    )
    payload = {
        "scorer": scorer.key(),
        "scores": {r.name: round(r.score, 1) for r in results if r.score is not None},
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (repo_root / _BASELINE_MD).write_text(rendered + "\n", encoding="utf-8")
    return path


def _render(
    scorer: Scorer,
    results: list[SkillScore],
    *,
    baseline: Baseline | None,
    no_baseline_note: str = "",
) -> str:
    """The advisory report: one row per skill, provenance named at the top.

    `no_baseline_note` overrides what an absent baseline says, because the two
    readers need opposite advice: a console run should be told to write one,
    while the committed baseline document IS the thing that would be written and
    telling it to write one reads as a defect.
    """
    scored = [r for r in results if r.score is not None]
    lines = [
        "# Skill scores — plugin-eval static layer (ADVISORY)",
        "",
        # The KEY, not the label: this table is committed, and an absolute home
        # path in a tracked file churns on every machine that regenerates it.
        f"Scorer: {scorer.key()}",
        "",
        "| Skill | Score | Δ | Anti-patterns | Weakest reachable dimension | Note |",
        "|---|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: (x.score is None, -(x.score or 0.0), x.name)):
        cell = f"{r.score:.1f}" if r.score is not None else "—"
        # The multiplier rides along with the flags: it is the only term that
        # explains a composite moving against every dimension in the report.
        found = ", ".join(r.anti_patterns) if r.anti_patterns else "0"
        if r.penalty != 1.0:
            found += f" (x{r.penalty:g})"
        note = r.error or ("vendored — regenerated by `kb-currency`" if r.vendored else "")
        delta = baseline.delta(r, scorer) if baseline else "—"
        lines.append(f"| `{r.name}` | {cell} | {delta} | {found} | {r.weakest or '—'} | {note} |")
    lines.append("")
    if baseline and baseline.scorer != scorer.key():
        # Never silently drop the comparison: a Δ column of dashes with no reason
        # given reads as "nothing changed", which is the opposite of the truth.
        lines.append(
            f"No Δ — the baseline was recorded by `{baseline.scorer}`, a different scorer."
        )
        lines.append("")
    elif not baseline:
        lines.append(
            no_baseline_note
            or f"No Δ — no committed baseline at `{_BASELINE_JSON}`; write one with `--write`."
        )
        lines.append("")
    if scored:
        mean = sum(r.score or 0.0 for r in scored) / len(scored)
        lines.append(f"{len(scored)} of {len(results)} scored; mean **{mean:.1f}/100**.")
    else:
        # Never "0.0 average". A run that measured nothing reports that it
        # measured nothing — the SKIP-is-not-OK rule the currency engine is
        # built on, applied here.
        lines.append("**NOT VERIFIABLE HERE** — no skill produced a score.")
    lines.append("")
    lines.append("Advisory: a score never fails a gate. Read the **Δ**, not the score — an")
    lines.append(
        "absolute number has no floor behind it. Re-baseline with "
        f"`mise run kb-skill-score -- --write` (`{_BASELINE_JSON}`)."
    )
    return "\n".join(lines)


class BadRequestError(ValueError):
    """A malformed invocation — rc 2, never a measurement outcome.

    Kept distinct from every "could not measure" path so the two cannot be
    collapsed by a later edit: advisory governs findings, and a request nobody
    can honour is not a finding.
    """


def parse_request(argv: list[str], repo_root: Path) -> tuple[list[Path], bool]:
    """`(skill directories to score, whether to re-baseline)`, or raise `BadRequestError`.

    Validated BEFORE the scorer is resolved, deliberately: a typo is a typo on a
    machine that has no plugin-eval installed too, and reporting
    NOT VERIFIABLE HERE for a misspelled name would send the reader off to
    install a plugin that was never the problem.
    """
    names = [a for a in argv if not a.startswith("-")]
    # Unrecognised flags are rejected, not ignored. Splitting argv on a leading
    # `-` silently swallowed every typo: a misspelled `--write` dropped out of
    # `names`, never matched the exact `"--write"` test, and ran an ordinary
    # scoring pass at rc 0 — the same output as a well-formed request, having
    # done none of what was asked. The name check below already refuses a typo'd
    # SKILL; a bad FLAG has to be refused by the same rule, or the rule is only
    # half applied.
    bad_flags = [a for a in argv if a.startswith("-") and a not in _FLAGS]
    if bad_flags:
        raise BadRequestError(
            f"unknown option {', '.join(repr(f) for f in bad_flags)}; "
            f"accepted: {', '.join(sorted(_FLAGS))}"
        )
    write = "--write" in argv
    if write and names:
        # A baseline is the FULL table or it is a trap: writing one from a
        # single-skill run would silently delete every other skill's recorded
        # score, and the next full run would report six `new` rows as though
        # nothing had ever been measured.
        raise BadRequestError("--write records the whole table; drop the skill names")
    targets, unknown = skill_dirs(repo_root, names or None)
    if unknown:
        known = ", ".join(sorted(p.name for p in skill_dirs(repo_root)[0])) or "(none)"
        raise BadRequestError(
            f"unknown skill {', '.join(repr(n) for n in unknown)}"
            f" under {_SKILLS_DIR}; present: {known}"
        )
    return targets, write


def main(argv: list[str], repo_root: Path) -> int:
    """`mise run kb-skill-score [--write] [-- <skill>...]`.

    Returns 0 for every measurement outcome, including "nothing here could
    measure anything" — advisory means a score never fails a caller's gate. It
    returns **2** for a malformed request, the same split `currency.run` draws
    for an unknown `--tool`. Three shapes count as malformed: an unrecognised
    flag, a skill name that matches nothing, and a `--write` that cannot record
    a complete table.
    """
    try:
        targets, write = parse_request(argv, repo_root)
    except BadRequestError as exc:
        print(f"[skill-score] {exc}", file=sys.stderr)
        return 2
    if not targets:
        print(f"[skill-score] no skill directories under {_SKILLS_DIR}", file=sys.stderr)
        return 0

    scorer = resolve_scorer(repo_root)
    if scorer is None:
        print(
            "[skill-score] NOT VERIFIABLE HERE — no plugin-eval checkout found.\n"
            "  Looked for: "
            + ", ".join(raw for _, raw in _PLUGIN_ROOTS)
            + "\n  The pinned clone appears after `mise run kb-build`; the marketplace copy\n"
            "  appears once `plugin-eval@claude-code-workflows` is installed and trusted.",
            file=sys.stderr,
        )
        return 0
    if shutil.which("uv") is None:
        print("[skill-score] NOT VERIFIABLE HERE — `uv` is not on PATH.", file=sys.stderr)
        return 0

    print(f"[skill-score] scored by {scorer.label()}", file=sys.stderr)
    vendored = vendored_names(repo_root)
    results: list[SkillScore] = []
    for target in targets:
        try:
            results.append(score_one(scorer, target, vendored=target.name in vendored))
        except subprocess.TimeoutExpired:
            # The static layer is documented as <2s. A timeout here means the
            # subprocess wedged, which is a fact about this run and must not be
            # laundered into a missing row.
            results.append(
                SkillScore(
                    name=target.name,
                    score=None,
                    error=f"timed out after {_SCORE_TIMEOUT_S:.0f}s",
                )
            )
    previous = load_baseline(repo_root)
    print(_render(scorer, results, baseline=previous))
    if write:
        try:
            path = write_baseline(repo_root, scorer, results, previous=previous)
        except ValueError as exc:
            # The table above still printed, so the reader sees WHICH skill failed
            # and why. What they do not get is a baseline missing that skill's
            # history — one transient timeout would otherwise erase a score
            # silently and report it as `new` on the next run.
            print(f"[skill-score] {exc}", file=sys.stderr)
            return 2
        print(f"\n[skill-score] baseline written to {path.relative_to(repo_root)}")
    return 0
