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

**ADVISORY — this always exits 0**, same posture as `kb-currency` and
`kb-goal-check`. We have no baseline yet, so any floor picked today would be
invented rather than measured; `zero-skip-policy.md` would then force sessions
to chase a number nobody validated. Ray's call, 2026-08-03: *"advisory now,
ratchet later"*. Read the table, not the rc.

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

#: `graphify/` is installer-generated (`graphify install --project`), >700 lines,
#: and never hand-edited — `md-size-budgets.md` exempts it from the markdown
#: budget for exactly that reason. It is still SCORED (a vendored skill we ship
#: is one we are judged by), but flagged, so nobody spends a round "fixing" a
#: file the next `kb-currency` bump overwrites.
_VENDORED = frozenset({"graphify"})

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

    def label(self) -> str:
        """One line naming the scorer, so two runs can be told apart."""
        return f"plugin-eval {self.version or '(version unknown)'} [{self.origin}: {self.root}]"


@dataclass(frozen=True)
class SkillScore:
    """One skill's static score, or the reason it has none."""

    name: str
    score: float | None
    anti_patterns: tuple[str, ...] = ()
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


def _version_of(root: Path) -> str:
    """`plugin-eval`'s own declared version, or "" when it cannot be read."""
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return ""
    match = _VERSION_RE.search(text)
    return match.group(1) if match else ""


def skill_dirs(repo_root: Path, names: list[str] | None = None) -> list[Path]:
    """Project skill directories to score, sorted for a stable table.

    A directory only counts when it holds a `SKILL.md`: `.claude/skills/` also
    accumulates `references/` and `scripts/` subtrees belonging to a skill, and
    handing one of those to `plugin-eval` would score a fragment as if it were a
    skill.
    """
    base = repo_root / _SKILLS_DIR
    if names:
        wanted = [base / n for n in names]
    else:
        wanted = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
    return [p for p in wanted if (p / "SKILL.md").is_file()]


def score_one(scorer: Scorer, skill_dir: Path) -> SkillScore:
    """Run the static layer over one skill directory."""
    name = skill_dir.name
    vendored = name in _VENDORED
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
    return SkillScore(
        name=name,
        score=float(raw),
        anti_patterns=_anti_patterns(data),
        weakest=_weakest(data),
        vendored=vendored,
    )


def _anti_patterns(data: Mapping[str, object]) -> tuple[str, ...]:
    """Anti-pattern names, gathered across every layer that ran.

    They live per-layer (`layers[].anti_patterns`) rather than at the top level,
    so a top-level lookup silently returns none — a count of 0 that means "not
    where I looked", not "none found". Exactly the shape of false-green this
    repo's probe rule exists to stop, which is why it is read per-layer here.
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
                label = item.get("name") or item.get("type") or item.get("pattern")
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


def _render(scorer: Scorer, results: list[SkillScore]) -> str:
    """The advisory report: one row per skill, provenance named at the top."""
    scored = [r for r in results if r.score is not None]
    lines = [
        "# Skill scores — plugin-eval static layer (ADVISORY)",
        "",
        f"Scorer: {scorer.label()}",
        "",
        "| Skill | Score | Anti-patterns | Weakest reachable dimension | Note |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(results, key=lambda x: (x.score is None, -(x.score or 0.0), x.name)):
        cell = f"{r.score:.1f}" if r.score is not None else "—"
        found = ", ".join(r.anti_patterns) if r.anti_patterns else "0"
        note = r.error or ("vendored — regenerated by `kb-currency`" if r.vendored else "")
        lines.append(f"| `{r.name}` | {cell} | {found} | {r.weakest or '—'} | {note} |")
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
    lines.append("Advisory: this never fails a gate. Compare a score to a PREVIOUS score of the")
    lines.append("same skill by the same scorer; an absolute number has no floor behind it yet.")
    return "\n".join(lines)


def main(argv: list[str], repo_root: Path) -> int:
    """`mise run kb-skill-score [-- <skill>...]` — always returns 0 (advisory)."""
    names = [a for a in argv if not a.startswith("-")]
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

    targets = skill_dirs(repo_root, names or None)
    if not targets:
        print(f"[skill-score] no skill directories under {_SKILLS_DIR}", file=sys.stderr)
        return 0

    results: list[SkillScore] = []
    for target in targets:
        try:
            results.append(score_one(scorer, target))
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
    print(_render(scorer, results))
    return 0
