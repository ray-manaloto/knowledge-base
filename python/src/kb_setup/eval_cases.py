"""This repo's eval cases — tier 1 (reachability) and tier 2 (guard fixtures).

The runner (:mod:`kb_setup.evals`) is shared; the CASES are per-repo, because
what "resolves" means differs. Here it means: the orchestration lanes the
doctrine names are reachable or their degradation is written down, the plugin's
own lane doctor can be reached, and the graph — this repo's entire reason to
exist — actually answers.

Tier 2 asks the next question again: not *does the guard exist* (tier 0's
contract) and not *is it wired* (the settings.json hook), but **does the wired
guard DECIDE correctly?** :data:`GUARD_FIXTURES` is the corpus, and its
must-ALLOW half is not decoration — it found two live false positives in
`kb_setup.hook_guard` on the day it was written (see that module).

Every gated case below carries a ``control``: the same probe logic pointed at
deliberately-broken input, which MUST come back FAIL. The runner refuses to
count a gated case whose control does not fail, so a case added here without a
real control arm turns the run red rather than quietly passing.

Writing those controls is where the work is, and it is worth stating the trap
that shows up immediately: **a control that returns SKIP is not armed.** The
obvious control for the graph canary — point it at a graph path that does not
exist — produces SKIP by design (an absent graph is expected on a fresh clone),
so it proves nothing. The controls below therefore build a real broken fixture
and drive the same code path against it.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from kb_setup import evals, hook_guard

#: Lane CLIs the routing doctrine names. `grok` is deliberately included and is
#: NOT installed — the doctrine says availability is discovered at run time, so
#: the case asserts the degradation path is DECLARED, not that grok exists.
DECLARED_LANES = ("codex", "agy", "grok")

#: Tokens whose presence constitutes "the degradation path is written down".
FALLBACK_TOKENS = ("fallback", "not installed")

#: The plugin's own lane doctor. Version-pinned inside the plugin cache, so it
#: can vanish on plugin GC — which is why the probe SKIPs loudly rather than
#: silently when it is absent.
DOCTOR_SCRIPT = Path.home().joinpath(
    ".claude/plugins/cache/fable-orchestrator/fable-orchestrator/1.14.0/scripts/doctor.sh"
)

#: A question the corpus must be able to answer at all. Deliberately NOT phrased
#: by echoing node labels — a label-echoing query grades lexical overlap and
#: reports a win that isn't there. This is only a liveness canary; real
#: retrieval quality is tier 2.
CANARY_QUESTION = "how are sources added to this knowledge base?"

_MISSING_BINARY = "definitely-not-a-real-binary-xyz"

_D = evals.GuardFixture
_DENY = evals.Decision.DENY
_ALLOW = evals.Decision.ALLOW

#: The tier-2 corpus for `kb_setup.hook_guard`: every row a real command shape,
#: with the decision it MUST get. Both halves are mandatory (the engine fails a
#: single-direction table), and the control arm runs this same table inverted.
#:
#: The must-ALLOW half is the load-bearing one. `_ALLOWED_READONLY`
#: (path/explain/god-nodes/affected/diagnose) is the surface a careless pattern
#: breaks, and the grep rows below are not hypothetical — both DENIED before the
#: fix that shipped with this table.
GUARD_FIXTURES: tuple[evals.GuardFixture, ...] = (
    # --- must DENY: every mutating / LLM-spending / task-equivalent subcommand
    _D("graphify add https://example.com/a", _DENY, "ingest goes through kb-add"),
    _D("graphify update mysource", _DENY, "re-ingest goes through kb-update"),
    _D('graphify query "how does x work"', _DENY, "retrieval goes through kb-query"),
    _D("graphify extract", _DENY, "extraction goes through kb-build"),
    _D("graphify merge-graphs", _DENY, "merges go through kb-build/kb-merge"),
    _D("graphify label", _DENY, "clustering goes through kb-label"),
    _D("graphify install --project", _DENY, "install mutates config — never by hand"),
    _D("graphify watch", _DENY, "watch is a do-not in this repo"),
    _D("graphify hook install", _DENY, "hook install is a do-not in this repo"),
    _D("graphify frobnicate", _DENY, "an UNKNOWN subcommand denies — the generic arm"),
    _D("cd /tmp && graphify extract", _DENY, "a cd prefix does not launder it"),
    _D("for f in a b; do graphify update $f; done", _DENY, "`do` is a command position"),
    _D("FOO=1 graphify add https://example.com/a", _DENY, "an env prefix does not launder it"),
    _D(
        "python python/src/kb_setup/_merge_docs.py chunk",
        _DENY,
        "the merge helper is kb-merge's job, not a hand-run script",
    ),
    _D(
        "~/.local/share/mise/installs/pipx-graphifyy/0.9.26/bin/python -c 'print(1)'",
        _DENY,
        "graphify's BUNDLED interpreter at command position",
    ),
    _D(
        'python -c "import graphify; print(graphify.__file__)"',
        _DENY,
        "a python head driving graphify — the payload is quoted here, on purpose",
    ),
    # --- must ALLOW: read-only introspection, the canonical tasks, and prose
    _D("graphify path a b", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify explain kb_setup", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify god-nodes", _ALLOW, "_ALLOWED_READONLY — no task equivalent"),
    _D("graphify affected python/src/kb_setup/evals.py", _ALLOW, "_ALLOWED_READONLY"),
    _D("graphify diagnose", _ALLOW, "_ALLOWED_READONLY"),
    _D(
        "graphify --help",
        _ALLOW,
        "allowed by FALL-THROUGH (the subcommand group needs a letter), not by "
        "_ALLOWED_READONLY — whose --help/-h/--version entries are unreachable",
    ),
    _D('mise run kb-query -- "how are sources added?"', _ALLOW, "the canonical task"),
    _D("mise run kb-build", _ALLOW, "the canonical task"),
    _D(
        'grep -rn "import graphify" python/',
        _ALLOW,
        "FALSE POSITIVE, measured 2026-07-25 — grepping FOR the pattern denied",
    ),
    _D(
        'rg "_merge_docs.py" .',
        _ALLOW,
        "FALSE POSITIVE, measured 2026-07-25 — same shape, same fix",
    ),
    _D('rg "graphify add" docs/', _ALLOW, "a quoted mention is not a command position"),
    _D('echo "do not run graphify add by hand"', _ALLOW, "prose describing the ban"),
    _D(
        'git commit -m "docs: explain why graphify update is denied"',
        _ALLOW,
        "a commit message describing the ban — dotfiles hit exactly this in #176",
    ),
    _D(
        'rg "import graphify" . ; python -c "print(1)"',
        _ALLOW,
        "the python head and the payload are in DIFFERENT segments",
    ),
    _D("uv run pytest tests/ -x -q", _ALLOW, "an ordinary uv command is untouched"),
    _D("git status --short", _ALLOW, "an unrelated command is untouched"),
)


def _broken_graph_canary() -> evals.Outcome:
    """Control arm: drive the canary against a graph that cannot answer.

    A directory holding a syntactically-present but meaningless ``graph.json``
    passes the existence gate (so this is not a SKIP) and then makes the real
    ``graphify query`` fail — which is the FAIL branch the canary must be shown
    to be able to reach.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        graph = root / "graphify-out" / "graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("not a graph")
        return evals.graphify_canary(root, CANARY_QUESTION, timeout=30)


def _broken_doctor() -> evals.Outcome:
    """Control arm: a doctor script that reports a failing lane.

    Distinct from the absent-script case on purpose. "We could not look" (SKIP)
    and "we looked and a lane is broken" (FAIL) must never collapse into each
    other, so the control exercises the second.
    """
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "doctor.sh"
        script.write_text("#!/usr/bin/env bash\necho '0 ok, 0 warnings, 1 failures'\nexit 1\n")
        return evals.doctor_health(script, timeout=30)


def _graphify_installed() -> evals.Outcome | None:
    """Environment gate: the canary cannot run where graphify is not installed.

    graphify is host-only in the sibling dotfiles repo, so inside its
    devcontainer this case asserts something that cannot be true. That is "does
    not apply here", not "the graph is broken" — and it must be a precondition
    rather than a SKIP inside the probe, because the control arm drives the same
    code path and would skip too, leaving the case UNARMED.
    """
    if shutil.which("graphify") is None:
        return evals.skip(
            "graphify is not installed in this environment (it is host-only in "
            "the consuming repo) — the canary cannot look, which is not the same "
            "as the graph having nothing to say"
        )
    return None


def cases(repo_root: Path, *, doctor_script: Path | None = None) -> list[evals.Case]:
    """Build this repo's tier-1 cases."""
    doctor = doctor_script if doctor_script is not None else DOCTOR_SCRIPT
    fallback_doc = repo_root / ".claude" / "CLAUDE.md"

    return [
        evals.Case(
            name="tier1.lanes-declared-or-degraded",
            description=(
                "every lane the doctrine names either resolves on PATH, or its "
                "degradation path is written down"
            ),
            probe=lambda: evals.declared_lanes_reconcile(
                DECLARED_LANES,
                fallback_doc=fallback_doc,
                fallback_tokens=FALLBACK_TOKENS,
            ),
            # Same logic with the fallback doc pointed at a file that does not
            # exist: "we cannot read the fallback" must never read as "declared".
            control=lambda: evals.declared_lanes_reconcile(
                (_MISSING_BINARY,),
                fallback_doc=repo_root / ".claude" / "does-not-exist.md",
                fallback_tokens=FALLBACK_TOKENS,
            ),
        ),
        evals.Case(
            name="tier1.graphify-resolves",
            description="the graphify CLI this repo drives resolves on PATH",
            probe=lambda: evals.cli_present("graphify"),
            control=lambda: evals.cli_present(_MISSING_BINARY),
        ),
        evals.Case(
            name="tier1.graph-answers",
            description=(
                "the graph does not merely exist — it returns a non-empty answer "
                "(rc=0 with empty output is a corpus that reads as healthy and "
                "knows nothing)"
            ),
            probe=lambda: evals.graphify_canary(repo_root, CANARY_QUESTION),
            control=_broken_graph_canary,
            precondition=_graphify_installed,
        ),
        evals.Case(
            name="tier1.lane-health",
            description=(
                "the plugin's own doctor.sh reports every installed lane "
                "authenticated with model access"
            ),
            probe=lambda: evals.doctor_health(doctor),
            control=_broken_doctor,
            # doctor.sh has NO offline mode: whenever a lane's CLI is present it
            # fires a real API call. So this is the live half, entirely, and can
            # never join the free gated tier — it runs only under --live.
            live=True,
        ),
        evals.guard_table_case(
            "tier2.guard-fixtures",
            "the PreToolUse graphify guard decides every fixture row as declared "
            "— both directions, since false positives are the only defect class "
            "ever measured in it",
            GUARD_FIXTURES,
            hook_guard.decide,
        ),
    ]
