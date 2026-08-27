# Copyright (c) 2026 Raymond Manaloto
"""Drive graphify's OWN native deep extraction over the pinned graphify clone.

## UNPARKED 2026-08-26 — the CLI subcommand and mise task are wired again

The `graphify-native-extract` CLI subcommand and the `kb-graphify-native-extract`
mise task were REMOVED on 2026-08-24 and RESTORED on 2026-08-26 (`cli.py::_run`,
`mise.toml:711`), once the three blocking defects the park existed to contain
(below) were closed. Both now reach this module: `uv run kb-setup
graphify-native-extract [...]` dispatches straight to `native_extract_main`, and
`mise run kb-graphify-native-extract` runs that same command. Neither exits with
"unknown command" any more — a message elsewhere in this file that still claims
otherwise is stale prose, not a description of the current wiring.

While parked, a direct Python import — `from kb_setup import
graphify_native_extract`, calling `native_extract_main`, or `_run_real`/
`_run_cluster` directly, bypassing `_parse` and `_refuse_out` entirely — was the
ONLY way in. The test suite does exactly that, deliberately, and still does: it
remains a valid path, just no longer the sole one.

The cold cross-family review of `fa4ed551ac7e` confirmed three blocking defects.
**All three are CLOSED as of 2026-08-25**, each armed rather than argued —
`docs/research/reports/2026-08-25-native-extract-unpark-arms.toml`, 6/6 died,
1/1 control held:

* **#479** — `_parse` took the token after `--out` as its value without asking
  whether that token is a flag, so `--out --dry-run` set `dry_run=False` and ran
  a REAL, token-spending extraction into a directory named `--dry-run`. Closed by
  `_flag_value`, which refuses a flag or an absent value — and applied to all
  FIVE value-taking flags, not only the one the review cited.
* **#480** — `_refuse_out` validated the `--out` flag, but `graphify/paths.py`
  reads `GRAPHIFY_OUT` from the environment (`paths.py:26`) and `clean_env()`
  passed it through, so the output root could be relocated without ever meeting
  the guard. Closed in TWO places for two different callers: `resolve_env` pops
  it (the direct-import caller meets no argv guard at all) and `_refuse_out`
  refuses it (silently overriding a deliberate export is its own defect).
* **#481** — `_run_real` and `_run_cluster`, the only functions that spawn the
  subprocess, had no coverage: replacing both bodies with `return 0` left all
  42 tests green. Closed by tests that replace `subprocess.run` itself and assert
  the argv, the cwd, the env and the propagated exit code — the same technique
  the `--artifacts` tests already used one layer up, so the "NO provider call,
  ever" promise below is untouched. That probe is now arms B4/B5.

**The park itself was a SEPARATE decision from closing the three defects, and it
is the one that took two extra days.** The three defects being closed
(2026-08-25) was the stated precondition for un-parking, not the reason to do
it: reviving this module at all is a decision rather than a repair, and the
ranking below says the SDK path supersedes it. The question that had to be
answered first was whether the SDK route had arrived.

**It has, for this verb.** `graphify.llm.extract_corpus_parallel` is pinned in
`kb_setup.graphify_sdk._SEMANTIC_SYMBOLS` with a reviewed signature carrying
`backend: str` and `model: str | None` as native parameters — **pinned but never
called**: no caller exists in `python/src/` or `tests/`. So the coupled-constants
problem this module has (below) does not exist on that path at all, because
neither backend nor model travels by environment variable there.

## Why this exists

**This is now the ONLY semantic-extraction path in the repo — and it is a
STOPGAP, not the destination.** Read the ranking before changing anything here
(Ray, 2026-08-24):

1. **Best — call graphify's PUBLIC SDK directly**, 1:1 with the CLI verb.
   `graphify_baseline.py` already does this through `kb_setup.graphify_sdk`,
   which exists precisely to pin that public surface
   (`graphify_sdk.public_api_fingerprint()`).
2. **Fallback — shell out to the CLI**, which is what THIS module does, for
   verbs graphify does not yet expose as public SDK methods.
3. **Never — import graphify's private internals.**

So this module should SHRINK over time, not grow: as graphify promotes a verb to
its public API, the call moves from here to a `graphify_sdk` seam. Do not read
"the only path" as "the preferred shape".

Until 2026-08-24 there was a second path, and it died on rule 3. A bespoke
eight-module layer (`graphify_semantic_corpus*.py`, `graphify_semantic_slice.py`,
`graphify_semantic_adapter.py`) imported `_estimate_file_tokens`,
`_extraction_system`, `_pack_chunks_by_tokens` and `_read_files` from
`graphify.llm` — four private functions — and re-implemented planning, slicing
and provider calls around them. Archived and explained in
`docs/archive/README.md`.

Two facts about that layer are worth keeping, because they are why this module
was written and why the ruling went the way it did:

- **It never got cheaper on a second run.** An AST walk of the pinned 0.9.45
  found no cache read anywhere in `extract_corpus_parallel`'s call chain from
  that entry point, only the checkpoint WRITER — so a restart re-bought the
  whole corpus at full price.
- **It drifted.** It copied assumptions out of graphify's internals, and those
  expired silently when graphify changed: `.html` joined
  `_SPLITTABLE_TEXT_SUFFIXES` (#2900), a 1.85 MB excluded file went from one
  unit to ~93, and 24 tests went red on an assumption nobody had touched.

This module calls graphify's own `extract` verb directly —
`graphify extract sources/graphify --mode deep --backend claude-cli` — which
IS the code path with the semantic-deep cache namespace behind it
(`graphify/cli.py`'s deep-mode block: "Deep mode reads/writes its own cache
namespace (cache/semantic-deep/)"). Run 2 onward over an unchanged tree
should be near-free through that cache; the removed layer's per-chunk driver
never touched it.

**Confirmed by a real run, 2026-08-23**: `--allow-parallel-claude-cli
--max-concurrency 4` completed 19/19 chunks (three split-and-retried by
graphify's own adaptive retry) and wrote 13,442 nodes / 26,791 edges / 692
communities to `.agent/kb/native-extract/`, rc=0. See the
`GRAPHIFY_CLAUDE_CLI_PARALLEL` section below for what that run does and does
not establish.

`--cluster` reruns graphify's own `cluster-only <out-dir>` verb against an
already-extracted `--out` tree (no `graph.json` there yet is a refusal, not a
silent no-op) — the step graphify's own `extract` output names as "next" to
get `GRAPH_REPORT.md` and named communities. It is independent of the extract
path: it never touches `opts.target`, runs under bare `clean_env()` with no
`--backend`, and is honoured under `--dry-run` too.

## What this does NOT do

It does not touch the aggregate `graphify-out/graph.json` —
`--out` always points outside both the repo root and the pinned clone (see
`_refuse_out` below). Merging this extraction's output into the aggregate
graph, if ever wanted, is a separate, later decision.

## The `GRAPHIFY_CLAUDE_CLI_PARALLEL` clamp: claim vs. what actually holds

`graphify/llm.py` (pinned v0.9.48, lines 2569 and 3301) force-serializes the
`claude-cli` backend — `max_concurrency` is clamped to 1 — UNLESS
`GRAPHIFY_CLAUDE_CLI_PARALLEL` is exactly `"1"`. graphify's own comments at
both sites give one reason: "claude-cli shells out to a Claude Code session;
parallel subprocesses conflict over session state" / "...a single Claude
Code session that parallel subprocesses corrupt." An earlier draft of this
module took that comment at face value and kept the override opt-in-only on
the strength of it. Two things have since undercut the claim itself,
not just the caution built on it:

1. **The argv graphify itself builds contradicts the stated mechanism.**
   Every `claude-cli` invocation — `_call_claude_cli` (extraction,
   `llm.py:1631` onward) and the labelling call site (`llm.py:2854`) — passes
   `--no-session-persistence` unconditionally, alongside `-p --output-format
   json`. There is no persisted session for concurrent subprocesses to
   contend over; each invocation is a one-shot, stateless CLI call. The
   comment describes a mechanism the code does not exhibit.
2. **The neighbouring clamp is evidenced; this one is not.** The `ollama`
   clamp two lines above cites a real defect (#798: four concurrent 60k-token
   requests cause VRAM pressure and hollow responses after 3-4 chunks). The
   `claude-cli` clamp cites no issue number — it reads as an unevidenced
   precaution, not a measured failure.
3. **It was measured, once, here.** With the clamp lifted
   (`--allow-parallel-claude-cli`, `--max-concurrency 4`), a real deep
   extraction of the pinned `sources/graphify` clone ran 19 chunks: 19 of 19
   completed, three timed out and were split-and-retried by graphify's own
   adaptive-retry path (not corrupted — retried and recovered), and the
   resulting graph (13,442 nodes, 26,791 edges, 692 communities) shows no
   corruption signature. A second run against the same output replayed 241
   cached units and re-extracted 133, rc=0 both times.

**What this licenses, stated at the strength the evidence supports — no
more.** The specific mechanism graphify's own comment names (persisted
session state) does not apply to how it invokes the CLI, and one 19-chunk
run at concurrency 4 on this machine completed cleanly. That is NOT
"parallel claude-cli is proven safe in general" — it is one run, one
machine, one corpus size. This module still keeps
`--allow-parallel-claude-cli` **opt-in** rather than flipping the default:
the evidence is real but it is n=1, and changing a default silently affects
every caller who has not looked at either this evidence or graphify's own
(now-contradicted) reasoning. Passing the flag is an informed choice
backed by the argv and the one completed run above, not a documented risk
being silently ignored — which is the correction to make, without
overcorrecting past what one run can support.

## The dry-run print is deliberately NOT the raw subprocess environment

A dry-run is meant to be safe to paste anywhere. `clean_env()` (which the
real run uses, and must, to keep every non-Claude backend trigger and mise's
secret blob out of the child) is still a COPY of the calling shell's entire
`os.environ` minus a specific named strip list — it is not credential-free
in general (a `GITHUB_TOKEN`, an `NPM_TOKEN`, anything mise's `[env]` block
resolved that isn't on the strip list, all pass through untouched). Printing
that whole dict on `--dry-run` would be exactly the "emit a credential value
to stdout" this repo's `secret_guard` hook exists to deny elsewhere — an
invariant that does not stop applying just because the emitter is our own
code rather than a shell one-liner. So the dry-run prints only the small
OVERLAY this module adds on top of the inherited environment — the CHOSEN
BACKEND's model variable and, opted in, its parallel one, derived by
`backend_env_keys` — never the full resolved dict handed to `subprocess.run`.

This sentence named `GRAPHIFY_CLAUDE_CLI_MODEL`/`_PARALLEL` unconditionally until
the round-2 cold lane read it against the code, which had been backend-derived
since `--backend` landed. It was the third and fourth place the same hardcoding
survived after the first two were fixed, and both were prose rather than
behaviour — which is exactly why they lasted: nobody re-reads a comment they
agree with.

## Verification scope

This module makes NO provider call, ever, including in its own tests. A human
runs the real extraction separately (multi-hour, serial-by-default, no timeout is
set here — the caller bounds it).

**That promise is about PROVIDER calls, and it was over-read as being about the
function bodies** — which is how #481 happened. This section used to say
`--dry-run` was the only path exercised for `extract`/`--cluster`, and the
justification it gave for the `--artifacts` exception applied to them verbatim:
*a reverted arg order would still print a correct-looking preview*. `_run_real`
and `_run_cluster` are now exercised for real with `subprocess.run` itself
replaced by a spy, so the argv, cwd, env and exit code are asserted and no process
ever starts. Dry-run coverage alone could not see a body replaced by `return 0`,
and for 42 tests it did not.

`--artifacts` is the one real (non-dry-run) path this suite DOES exercise,
because the thing worth proving — that `_run_artifacts` hands `repo_root` and
`opts.out` to `kb_setup.artifacts.generate` in the right roles (`repo_root` for
the exe/venv anchor, `opts.out` as `graph_root`) — is exactly the wiring a
`--dry-run` print string cannot verify on its own: a reverted arg order would
still print a correct-looking preview. `kb_setup.artifacts.generate` itself is
fully mocked in that test, so no graphify subprocess and no provider call ever
runs; it is a one-line wiring check, not a real extraction.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from kb_setup import events
from kb_setup.graphify_env import (
    assert_pinned_graphify,
    clean_env,
    graphify_exe,
    installed_backends,
)
from kb_setup.result import Rc

#: The pinned clone this task extracts — never this repo itself. Gitignored,
#: re-cloned at build time from `sources/graphify.manifest`.
DEFAULT_TARGET = "sources/graphify"

#: Deliberately OUTSIDE `sources/graphify` (writing into a gitignored,
#: re-cloneable pinned clone is the same class of defect #420 fixed for a
#: stray marker file) and OUTSIDE the repo root (which would place a
#: `graphify-out/` there and collide with the aggregate `kb-build` owns —
#: see `_refuse_out`). `.agent/` is this repo's gitignored scratch tree.
DEFAULT_OUT = ".agent/kb/native-extract"

#: Confirmed 2026-08-23: `claude --help` documents `--model <model>` as
#: accepting "a model's full name (e.g. 'claude-fable-5')" — the CLI's own
#: example proves the `claude-<tier>-5` spelling — and
#: `kb_setup.model_limits` (line ~375) independently recorded a live
#: `GET /v1/models/claude-opus-5` -> 200 on 2026-08-17. "Confirmed" means the
#: identifier's FORM: this module makes no provider call, so nothing here
#: sends a prompt to check it is accepted.
#:
#: ⚠️ THIS IS `claude-cli`'S MODEL, AND ONLY ITS MODEL — a distinction that did
#: not exist until `--backend` did, and was not made when it arrived. Applied
#: unconditionally it wrote `GRAPHIFY_OPENAI_CLI_MODEL=claude-opus-5`: a Claude
#: identifier into an OpenAI backend's own model variable, silently, on any run
#: that did not pass `--model`. graphify's table records that backend's default
#: as `gpt-5.6-sol`. Third instance of this branch's own defect class — one
#: value, several consumers that must agree — found by the round-2 cold lane
#: after the first two were fixed.
#:
#: Note it deliberately DIFFERS from graphify's own `claude-cli` default
#: (`claude-code-plan`): overriding that is the point of setting the variable at
#: all, and the paragraph above is why this identifier and not another.
DEFAULT_MODEL = "claude-opus-5"

#: `claude-cli`'s env keys, kept ONLY as the expected value in tests that assert
#: what the default backend resolves to. Production code must call
#: `backend_env_keys(opts.backend)` — these two constants are what `env_overlay`
#: used to read unconditionally, which is how the backend and its model variable
#: came apart. Naming them here rather than deleting them keeps the tests'
#: expectation legible; using them in `python/src/` would reintroduce the defect.
_MODEL_ENV = "GRAPHIFY_CLAUDE_CLI_MODEL"
_PARALLEL_ENV = "GRAPHIFY_CLAUDE_CLI_PARALLEL"

#: graphify/paths.py: `GRAPHIFY_OUT = os.environ.get("GRAPHIFY_OUT", "graphify-out")`.
#: graphify's default output-directory name.
#:
#: ⚠️ THIS COMMENT USED TO SAY the literal default is "the only value that can
#: apply to a run it starts", because this module never SETS the override. That
#: was #480: not setting a variable does not stop a subprocess INHERITING one,
#: and `clean_env()` passed `GRAPHIFY_OUT` straight through. The reasoning was
#: true and the conclusion was false — the sibling shape of every "unreachable
#: by construction" claim this repo has had to retract. `resolve_env` now pops
#: it, which is what makes the literal below actually the only value that applies.
_GRAPHIFY_OUT_NAME = "graphify-out"

#: The environment override `resolve_env` removes, named once so the pop and the
#: refusal message can never disagree about which variable is at issue (#480).
_GRAPHIFY_OUT_ENV = "GRAPHIFY_OUT"

#: The extraction backend when nothing asks for another. Claude, deliberately:
#: `do-not.md` #4 makes Claude the corpus's only LLM, and a default that had to
#: be opted OUT of would put an irreversible spending decision one typo away.
DEFAULT_BACKEND = "claude-cli"


@dataclass(frozen=True, slots=True)
class Options:
    """Resolved, absolute inputs to one native-extract invocation."""

    target: Path
    out: Path
    token_budget: int | None = None
    max_concurrency: int | None = None
    allow_parallel_claude_cli: bool = False
    #: The extraction backend, and with it the model/parallel env keys — ONE
    #: coupled choice (`backend_env_keys`), never three that can drift apart.
    backend: str = DEFAULT_BACKEND
    #: Empty means "the caller did not ask for one", which is NOT the same as
    #: `DEFAULT_MODEL` and could not be distinguished from it while that was the
    #: default here. `resolve_model` turns the absence into the right answer per
    #: backend — including "say nothing", which no non-empty default can express.
    model: str = ""
    dry_run: bool = False
    cluster: bool = False
    artifacts: bool = False
    artifacts_views: tuple[str, ...] = ()


class _UsageError(Exception):
    """Argv could not be parsed. Carries the message to print."""


def _consume_view_names(argv: list[str], start: int) -> tuple[tuple[str, ...], int]:
    """Every token from `start` that is not itself a flag, plus the next index.

    `--artifacts wiki graphml --dry-run` stops at `--dry-run`, mirroring how
    `kb-artifacts`'s own positional args already work (`cli.py`:
    `artifacts.generate(root, only=rest or None)`). An empty result (bare
    `--artifacts`) means "all", same as `only=None`.
    """
    views: list[str] = []
    i = start
    while i < len(argv) and not _looks_like_flag(argv[i]):
        views.append(argv[i])
        i += 1
    return tuple(views), i


def _looks_like_flag(token: str) -> bool:
    """Whether `token` reads as a flag rather than as a value.

    ONE predicate with two callers, deliberately. `_consume_view_names` already
    had to answer this question to know where a view list ends; `_flag_value`
    below has to answer the same question to know a value was omitted. Two
    spellings of one rule in one file is how the identical defect survives in
    the half nobody edited — this repo has now paid for that twice (#245, #499).

    `--` rather than `-`: every flag this parser recognises is `--`-prefixed, so
    this catches both a recognised flag and an unrecognised `--typo`, while
    leaving an odd-but-deliberate single-dash value (a path, a model name)
    usable.
    """
    return token.startswith("--")


def _flag_value(argv: list[str], i: int, flag: str) -> str:
    """The value token after `flag` at index `i`, refusing a flag or an end (#479).

    The defect this closes was live and expensive in exactly one direction:
    `--out --dry-run` took `--dry-run` as the OUT PATH and consumed it, so
    `dry_run` stayed `False` and a REAL, token-spending extraction ran into a
    directory named `--dry-run`. The user's typo asked for a preview and got a
    bill. Refusing is the only safe reading — there is no plausible run in which
    someone means a directory named after a flag.

    The end-of-argv case was not dangerous but was misdescribed: a trailing
    `--out` fell through the whole chain to the `else`, reporting
    `unrecognised argument: '--out'` about a flag this parser recognises
    perfectly well, which sends the reader to check their spelling instead of
    their missing value.
    """
    if i + 1 >= len(argv):
        raise _UsageError(f"{flag} requires a value")
    value = argv[i + 1]
    if _looks_like_flag(value):
        raise _UsageError(
            f"{flag} requires a value, but the next argument is the flag {value!r} — "
            f"if you meant both, put the value first"
        )
    return value


#: Flags that take no value and just flip a `bool` field on `Options` — kept as
#: data rather than more `elif` branches so `_parse` stays under the repo's
#: cyclomatic-complexity gate as flags are added.
_BOOL_FLAGS = {
    "--allow-parallel-claude-cli": "allow_parallel_claude_cli",
    "--dry-run": "dry_run",
    "--cluster": "cluster",
}

#: Flags that take a value, as `flag -> (Options field, how to read the token)`.
#:
#: Data for the same reason `_BOOL_FLAGS` above is data, and the comment there
#: predicted exactly what happened: adding `--backend` as a sixth `elif` pushed
#: `_parse` to cyclomatic 11 against a ceiling of 10. The honest fix for "one
#: more branch" is the table the file already reaches for, never a suppression
#: (`do-not.md` #9).
#:
#: The reader is `(repo_root, flag, raw) -> value` so a path can be anchored and
#: an int validated without the caller knowing which is which — and every entry
#: goes through `_flag_value` first, so #479's refusal covers a new flag by
#: construction rather than by whoever adds it remembering to.
_VALUE_FLAGS = {
    "--out": ("out", lambda root, _f, raw: root / raw),
    "--target": ("target", lambda root, _f, raw: root / raw),
    "--token-budget": ("token_budget", lambda _r, f, raw: _parse_positive_int(f, raw)),
    "--max-concurrency": ("max_concurrency", lambda _r, f, raw: _parse_positive_int(f, raw)),
    "--model": ("model", lambda _r, _f, raw: raw),
    "--backend": ("backend", lambda _r, _f, raw: raw),
}


def _parse(repo_root: Path, argv: list[str]) -> Options:
    # Defaults come from `Options` itself and are applied by `replace` at the
    # bottom, so this function holds only what argv actually asked for. The
    # previous shape restated every default as a local, which is a second place
    # for a default to live and therefore a second place for one to drift.
    base = Options(target=repo_root / DEFAULT_TARGET, out=repo_root / DEFAULT_OUT)
    fields: dict[str, object] = {}
    artifacts_requested = False
    artifacts_views: tuple[str, ...] = ()

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in _BOOL_FLAGS:
            fields[_BOOL_FLAGS[a]] = True
            i += 1
        elif a in _VALUE_FLAGS:
            field, read = _VALUE_FLAGS[a]
            fields[field] = read(repo_root, a, _flag_value(argv, i, a))
            i += 2
        elif a == "--artifacts":
            artifacts_requested = True
            artifacts_views, i = _consume_view_names(argv, i + 1)
        else:
            raise _UsageError(f"unrecognised argument: {a!r}")

    if fields.get("cluster") and artifacts_requested:
        raise _UsageError("pass at most one of --cluster / --artifacts")

    return replace(
        base,
        artifacts=artifacts_requested,
        artifacts_views=artifacts_views,
        # Every key is an `Options` field name, and the two flag tables above are
        # what guarantee it — a flag whose field does not exist raises here on the
        # first parse rather than silently defaulting.
        **fields,
    )


def _parse_positive_int(flag: str, raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise _UsageError(f"{flag} must be an integer (got {raw!r})") from exc
    if value <= 0:
        raise _UsageError(f"{flag} must be > 0 (got {value})")
    return value


def resolve_argv(exe: str, opts: Options) -> list[str]:
    """The graphify `extract` invocation this module runs.

    Used by both the dry-run preview and the real invocation, so they can
    never drift apart.
    """
    argv = [
        exe,
        "extract",
        str(opts.target),
        "--mode",
        "deep",
        "--backend",
        opts.backend,
        "--out",
        str(opts.out),
    ]
    if opts.token_budget is not None:
        argv += ["--token-budget", str(opts.token_budget)]
    if opts.max_concurrency is not None:
        argv += ["--max-concurrency", str(opts.max_concurrency)]
    return argv


def env_overlay(opts: Options) -> dict[str, str]:
    """The variables THIS module adds — the safe, printable subset.

    See the module docstring's dry-run section. Never the full subprocess env.
    """
    # Keyed on `opts.backend`, never on the module constants this used to read
    # (#499's sibling, one layer over). `--backend`, the model env and the
    # parallel env are ONE coupled choice: switching only the first left the
    # model override pointing at `GRAPHIFY_CLAUDE_CLI_MODEL`, which an
    # `openai-cli` run never reads — so `--model` went INERT while the dry-run
    # below kept printing it as though it had applied. Three constants that must
    # move together are not three settings; they are one, and they are derived
    # from one value here so they cannot be moved apart.
    model_env, parallel_env = backend_env_keys(opts.backend)
    overlay = {}
    model = resolve_model(opts)
    if model:
        overlay[model_env] = model
    if opts.allow_parallel_claude_cli:
        overlay[parallel_env] = "1"
    return overlay


def resolve_model(opts: Options) -> str:
    """The model to override with, or `""` to let graphify choose (round-2 lane).

    Three cases, and the third is the one that did not exist before `--backend`:

    1. `--model` was passed — use it, whatever the backend. The caller is
       explicit and this function does not second-guess them.
    2. No `--model`, backend is `claude-cli` — `DEFAULT_MODEL`. This repo has an
       opinion there, recorded beside that constant, and it deliberately differs
       from graphify's own `claude-code-plan`.
    3. No `--model`, any other backend — **say nothing**, and let graphify apply
       the default its own table records for that backend.

    Case 3 is the fix. `Options.model` used to default to `DEFAULT_MODEL`, so
    `env_overlay` wrote `GRAPHIFY_OPENAI_CLI_MODEL=claude-opus-5` — a Claude
    identifier into an OpenAI backend's own variable — on every run that did not
    pass `--model`. The env KEY was correctly derived from the backend by then;
    the VALUE under it was not, which is the same one-value-several-consumers
    defect one level in.

    Omitting beats substituting graphify's `default_model` here: that value
    already lives in graphify's table, and copying it into ours is precisely the
    second-copy-that-drifts this module has now been bitten by twice (#245, #499).
    Not setting the variable is how you say "use yours" without restating it.
    """
    if opts.model:
        return opts.model
    return DEFAULT_MODEL if opts.backend == DEFAULT_BACKEND else ""


def backend_env_keys(backend: str) -> tuple[str, str]:
    """`(model_env, parallel_env)` for `backend`, cross-checked against the table.

    Both follow one shape in graphify — `GRAPHIFY_<BACKEND>_MODEL` and
    `_PARALLEL`, with `-` becoming `_` — verified in its source for both CLI
    backends: `GRAPHIFY_CLAUDE_CLI_MODEL` is read at `llm.py:1776`,
    `GRAPHIFY_OPENAI_CLI_MODEL` at `:1885`, and the two `_PARALLEL` keys at
    `:2829-2831` and `:3628-3630`.

    Derived AND checked, rather than either alone, because neither source is
    complete on its own. The table is authoritative where it speaks — but
    `claude-cli` declares **no** `model_env_key` at all while graphify plainly
    reads one for it, so a table-only lookup returns nothing for the default
    backend. And a shape-only derivation would guess past a backend that names
    its variable differently. So: derive, then refuse if the table disagrees. A
    disagreement is upstream drift, and guessing past it is how a model override
    goes inert while the dry-run keeps printing it.
    """
    stem = "GRAPHIFY_" + backend.upper().replace("-", "_")
    model_env = f"{stem}_MODEL"
    declared = installed_backends().get(backend, {}).get("model_env_key")
    if declared and declared != model_env:
        raise _UsageError(
            f"backend {backend!r} declares model_env_key {declared!r} but this module "
            f"derives {model_env!r} — graphify's naming changed. Fix the derivation "
            f"rather than setting a variable the backend will never read."
        )
    return model_env, f"{stem}_PARALLEL"


def _refuse_backend(backend: str) -> str | None:
    """`None` if `backend` exists in the installed graphify; else the refusal.

    Fails closed on a spending regression, which is why it refuses rather than
    warns. `openai-cli` is a PATCH THIS FORK CARRIES, not upstream — its own
    comment in `llm.py` says that if an upgrade removes it "the backend silently
    disappears and extraction can fall back to the metered OpenAI API". A run
    that asked for a subscription-billed backend and silently got a metered one
    is an irreversible cost, and the only safe answer to "the backend you named
    is not here" is to not start.
    """
    backends = installed_backends()
    if backend in backends:
        return None
    return (
        f"[graphify-native-extract] refusing --backend {backend} — the installed "
        f"graphify has no such backend. Available: {', '.join(sorted(backends))}. "
        f"If you expected it, an upgrade may have dropped a fork-local patch; "
        f"`mise run kb-currency-check` reports that."
    )


def resolve_env(opts: Options) -> dict[str, str]:
    """The full environment the real subprocess runs under.

    `clean_env()` (every non-Claude backend trigger and mise's secret blob
    stripped) plus this module's overlay, with `GRAPHIFY_OUT` REMOVED (#480).
    Never printed in full — see `env_overlay`.

    `GRAPHIFY_OUT` is graphify's own output-root override
    (`graphify/paths.py:26`, `os.environ.get("GRAPHIFY_OUT", "graphify-out")`).
    `clean_env()` strips backend triggers and passes it through, so an ambient
    value relocated every write this module makes WITHOUT ever meeting
    `_refuse_out` — which reads `opts.out` and knows nothing about the
    environment. The guard was real and the lever went around it.

    Removed here rather than only refused in `native_extract_main`, because the
    two protect different callers and the module docstring is explicit that both
    exist: `_refuse_out` covers the argv path and gives a human a message they
    can act on, while this covers a caller who imports the module and invokes
    `_run_real` directly, meeting no argv guard at all. Neither alone closes it.
    """
    env = clean_env(env_overlay(opts))
    env.pop(_GRAPHIFY_OUT_ENV, None)
    return env


def _refuse_out(repo_root: Path, opts: Options) -> str | None:
    """`None` if `--out` is safe; otherwise the refusal message.

    Two distinct unsafe shapes, both checked against the RESOLVED (symlink-
    normalised) path so a relative detour cannot slip past a string
    comparison:

    1. `out == repo_root` — graphify would write `<repo_root>/graphify-out/`,
       which IS the aggregate graph `kb-build` owns. That is the class of
       defect this task exists to never cause.
    2. `out` inside `opts.target` (the pinned clone) — writing into a
       gitignored, re-cloneable checkout is the same class of defect #420
       fixed for a stray marker file: the next `mise run kb-build` re-clones
       over it with no warning that anything was lost.

    And one shape that is not about `--out` at all (#480): an ambient
    `GRAPHIFY_OUT`. `resolve_env` now removes it, so a run started here is safe
    either way — but silently ignoring a variable someone deliberately exported
    is its own defect, and the two answers ("your setting was overridden" vs
    "your setting relocated everything") are indistinguishable from the outside.
    Refusing says which one happened. Checked FIRST, because it is the one that
    invalidates the reasoning behind the other two rather than joining them.
    """
    # PRESENCE, not truthiness (cold lane, 14756ebb8212). `.strip()` treated an
    # empty-but-exported `GRAPHIFY_OUT=""` as absent — and that is the one value
    # worth refusing hardest: graphify reads it as `os.environ.get(..., "graphify-out")`
    # (`paths.py:26`), so an empty string is USED, giving an empty output-directory
    # NAME rather than falling back to the default. Exporting it is a deliberate
    # act; this guard exists to say so rather than to judge the value.
    ambient_out = os.environ.get(_GRAPHIFY_OUT_ENV)
    if ambient_out is not None:
        return (
            f"[graphify-native-extract] refusing to run with {_GRAPHIFY_OUT_ENV}="
            f"{ambient_out!r} in the environment — it relocates graphify's output root "
            f"({_GRAPHIFY_OUT_NAME}/) past every --out check this guard makes (#480). "
            f"Unset it and use --out, which is the one lever this task validates."
        )
    out = opts.out.resolve()
    root = repo_root.resolve()
    if out == root:
        return (
            f"[graphify-native-extract] refusing --out {opts.out} — it resolves to the "
            f"repo root ({root}), which would write {_GRAPHIFY_OUT_NAME}/ there and collide "
            "with the aggregate graph `mise run kb-build` owns. Pick a directory outside "
            "the repo root, or omit --out to use the default "
            f"({DEFAULT_OUT})."
        )
    target = opts.target.resolve()
    if out == target or target in out.parents:
        return (
            f"[graphify-native-extract] refusing --out {opts.out} — it resolves inside "
            f"the pinned clone ({target}), which is gitignored and re-cloned on every "
            "`mise run kb-build`. Pick a directory outside sources/graphify, or omit "
            f"--out to use the default ({DEFAULT_OUT})."
        )
    return None


def resolve_cluster_argv(exe: str, opts: Options) -> list[str]:
    """The graphify `cluster-only` invocation `--cluster` runs.

    `cluster-only <path>` takes the SAME output-directory shape `extract --out`
    wrote to — its own default `--graph` is `<path>/graphify-out/graph.json`
    (confirmed against the installed `graphify --help`, not assumed) — so this
    passes `opts.out` unchanged, never `opts.out / "graphify-out"`.

    No `--backend`/`--model` flag, ever: the deterministic hub labeller is
    what runs when no backend is named AND the environment carries no
    backend-selecting key, which `clean_env()` already guarantees (mirrors
    `graphify_ops.label()`'s own default path — see `resolve_cluster_env`).
    """
    return [exe, "cluster-only", str(opts.out)]


def resolve_cluster_env(opts: Options) -> dict[str, str]:
    """The environment `--cluster` runs under: bare `clean_env()`.

    Deliberately NOT `resolve_env(opts)` — that adds the CHOSEN BACKEND's model
    variable (and, opted in, its parallel one), which would be inert here (no
    `--backend` is ever passed to `cluster-only` from this module) but would
    misleadingly suggest an LLM labelling backend is in play. It said
    `GRAPHIFY_CLAUDE_CLI_MODEL` unconditionally until the round-2 cold lane
    checked it against `env_overlay`; that is only this variable when the backend
    is `claude-cli`. `opts` is accepted for
    signature symmetry with `resolve_env` even though it is currently unused.
    """
    del opts
    return clean_env()


def _cluster_graph_json(opts: Options) -> Path:
    """Where `cluster-only` expects to find an existing `graph.json`."""
    return opts.out / _GRAPHIFY_OUT_NAME / "graph.json"


def _refuse_cluster_input(opts: Options) -> str | None:
    """`None` if `--out` already holds a `graph.json` to work with.

    Otherwise the refusal message. Shared by BOTH `--cluster` and
    `--artifacts` (see `_dispatch_artifacts`) — `cluster-only` and every
    artifact generator are rerun-only verbs that have nothing to do over an
    output tree extraction never wrote to. Refusing (rather than letting
    graphify's own error surface, or silently no-op) keeps this in the same
    shape as `_refuse_target`: a run that never asked the question is not a
    pass.
    """
    graph_json = _cluster_graph_json(opts)
    if not graph_json.is_file():
        return (
            f"[graphify-native-extract] refusing — {graph_json} does not exist. "
            "`--cluster` reruns graphify's clustering step over an ALREADY "
            "extracted `--out` tree; it does not perform an extraction itself. "
            "Run `uv run kb-setup graphify-native-extract --out DIR [...]` (or "
            "`mise run kb-graphify-native-extract`) WITHOUT `--cluster` first to "
            "produce that tree, then rerun with `--cluster` pointed at the same "
            "`--out`."
        )
    return None


def _print_cluster_dry_run(exe: str, opts: Options) -> None:
    argv = resolve_cluster_argv(exe, opts)
    print("[graphify-native-extract] DRY RUN (--cluster) — nothing was invoked")
    print(f"  $ {' '.join(argv)}")
    print(
        "  environment: bare clean_env() — no --backend is passed, so this always runs "
        "graphify's deterministic, LLM-free hub labeller (no LLM, no API)."
    )


def _run_cluster(repo_root: Path, exe: str, opts: Options) -> int:
    # Same rationale as `_run_real`: checked here, the one place graphify
    # actually runs, never on the dry-run path.
    assert_pinned_graphify(repo_root)
    argv = resolve_cluster_argv(exe, opts)
    env = resolve_cluster_env(opts)
    print(f"[graphify-native-extract] $ {' '.join(argv)}")
    result = subprocess.run([*argv], cwd=repo_root, env=env, check=False)
    return result.returncode


def _refuse_target(opts: Options) -> str | None:
    """`None` if the target exists; otherwise the refusal message.

    The pinned clone is gitignored (`sources/graphify.manifest` re-clones it
    at build time) and may simply be absent on a fresh checkout. Absence is
    not a silent success and not a crash — it is a refusal that names the
    remedy, per this repo's standing rule that a run which never asked the
    question is not a pass.
    """
    if not opts.target.is_dir():
        return (
            f"[graphify-native-extract] refusing — target {opts.target} does not exist. "
            "Run `mise run kb-build` to re-clone the pinned sources first."
        )
    return None


def _print_dry_run(exe: str, opts: Options) -> None:
    argv = resolve_argv(exe, opts)
    overlay = env_overlay(opts)
    # Resolved ONCE and passed down, rather than re-derived inside the NOTE below.
    # Two calls could not disagree today (`backend_env_keys` is pure over
    # `opts.backend`), but "two derivations of one value that must agree" is the
    # exact shape this whole branch keeps finding defects in — including twice in
    # this function. Not worth leaving a fourth instance lying around.
    _, parallel_env = backend_env_keys(opts.backend)
    print("[graphify-native-extract] DRY RUN — nothing was invoked")
    print(f"  $ {' '.join(argv)}")
    print("  environment overlay (added on top of clean_env(); nothing else is printed —")
    print("  see the module docstring's dry-run section for why):")
    for key, value in sorted(overlay.items()):
        print(f"    {key}={value}")
    if not opts.allow_parallel_claude_cli:
        # Backend-aware, and it was not until the cold lane on 14756ebb8212 caught
        # it. This NOTE hardcoded `GRAPHIFY_CLAUDE_CLI_PARALLEL`, the words
        # "claude-cli runs serially", the claude-cli clamp's line numbers, AND the
        # claude-cli evidence — printed verbatim under `--backend openai-cli`.
        #
        # It is the SAME coupled-constants defect this commit fixed in
        # `env_overlay` one function above, surviving in the printer: a fix at one
        # layer leaves the next. Worse here than there, because the env overlay is
        # merely wrong while this is wrong OUT LOUD, in the one output a reader
        # consults to check what a run will do.
        print(
            f"  NOTE: {parallel_env} is NOT set — {opts.backend} runs serially "
            "(graphify's own default)."
        )
        # The evidence is claude-cli's and stays scoped to it. A 19-chunk run and
        # `--no-session-persistence` say nothing about another backend's clamp, and
        # carrying a true fact past its condition is how this repo has shipped
        # confident wrong claims before (`verify-before-advancing.md`).
        if opts.backend == DEFAULT_BACKEND:
            print(
                "  graphify's clamp comment (llm.py:2569/:3301) cites session-state "
                "conflict, but every claude-cli invocation passes "
                "--no-session-persistence, and a real 19-chunk run at concurrency 4 "
                "with the clamp lifted completed cleanly (see the module docstring). "
                "Pass --allow-parallel-claude-cli to lift it — an informed opt-in, "
                "not a workaround for a live risk."
            )
        else:
            print(
                f"  NO evidence either way for {opts.backend}: the run that cleared "
                "the clamp was claude-cli's, and it does not transfer. Lifting it "
                "here with --allow-parallel-claude-cli is untested, not informed."
            )


def _run_real(repo_root: Path, exe: str, opts: Options) -> int:
    # Checked here, not in the dry-run path: this is the one place graphify
    # actually runs, and a stale binary rewriting output under an unverified
    # version is the exact hazard `assert_pinned_graphify` exists to refuse
    # before any writer touches disk.
    assert_pinned_graphify(repo_root)
    argv = resolve_argv(exe, opts)
    env = resolve_env(opts)
    print(f"[graphify-native-extract] $ {' '.join(argv)}")
    # No capture_output: stdio is inherited so a human watching sees graphify's
    # own progress output live, exactly like `merge_chunk`'s subprocess call.
    # No timeout: the caller bounds this (long-running-command-hangs.md).
    result = subprocess.run([*argv], cwd=repo_root, env=env, check=False)
    return result.returncode


def _dispatch_cluster(repo_root: Path, exe: str, opts: Options) -> int:
    """`--cluster`: standalone, never touches `opts.target`.

    A missing pinned clone must not block re-clustering an output tree that
    already exists — this checks only `_refuse_cluster_input`.
    """
    cluster_problem = _refuse_cluster_input(opts)
    if cluster_problem:
        events.fail("graphify_native_extract.missing_cluster_input", cluster_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_cluster_dry_run(exe, opts)
        return Rc.OK
    return _run_cluster(repo_root, exe, opts)


def _dispatch_extract(repo_root: Path, exe: str, opts: Options) -> int:
    """The default mode: extract from `opts.target` into `opts.out`."""
    target_problem = _refuse_target(opts)
    if target_problem:
        events.fail("graphify_native_extract.missing_target", target_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_dry_run(exe, opts)
        return Rc.OK
    return _run_real(repo_root, exe, opts)


def _refuse_unknown_views(views: tuple[str, ...]) -> str | None:
    """`None` if every requested view name is one `artifacts.generate` knows.

    Without this, `--artifacts wiky` (a typo) matches ZERO entries in
    `artifacts._ARTIFACTS` — `generate`'s own `only=` filter silently narrows
    to an empty selection and reports "0 artifacts generated" / "all
    artifacts generated" as a CLEAN rc=0 run. That is exactly the "partial
    success reported as success" failure mode this repo cares most about, so
    an unrecognised name is refused here, before it ever reaches `generate`
    as a silent no-op.
    """
    if not views:
        return None
    from kb_setup import artifacts

    known = artifacts.known_views()
    unknown = [v for v in views if v not in known]
    if not unknown:
        return None
    return (
        f"[graphify-native-extract] refusing --artifacts {' '.join(unknown)} — "
        f"not a known view (known: {', '.join(known)})"
    )


def _print_artifacts_dry_run(repo_root: Path, opts: Options) -> None:
    views = ", ".join(opts.artifacts_views) if opts.artifacts_views else "all (default registry)"
    print("[graphify-native-extract] DRY RUN (--artifacts) — nothing was invoked")
    print(f"  views: {views}")
    print(f"  graph_root (data + cwd, never the aggregate graphify-out/): {opts.out}")
    print(f"  repo_root (graphify exe + venv anchor only): {repo_root}")
    print("  via kb_setup.artifacts.generate(repo_root, only=<views>, graph_root=<out>)")


def _run_artifacts(repo_root: Path, opts: Options) -> int:
    # Same rationale as `_run_real`/`_run_cluster`: checked here, the one place
    # graphify actually runs.
    assert_pinned_graphify(repo_root)
    from kb_setup import artifacts

    only = list(opts.artifacts_views) or None
    return artifacts.generate(repo_root, only=only, graph_root=opts.out)


def _dispatch_artifacts(repo_root: Path, opts: Options) -> int:
    """`--artifacts`: standalone, never touches `opts.target`.

    Reuses `kb_setup.artifacts.generate` rather than a second generator
    registry — see that function's `graph_root` docstring for why `repo_root`
    (never `opts.out`) still anchors `graphify_exe`/`ensure_runtime_deps`.
    """
    view_problem = _refuse_unknown_views(opts.artifacts_views)
    if view_problem:
        events.fail("graphify_native_extract.unknown_artifact_view", view_problem)
        return Rc.BAD_REQUEST
    artifacts_problem = _refuse_cluster_input(opts)
    if artifacts_problem:
        events.fail("graphify_native_extract.missing_artifacts_input", artifacts_problem)
        return Rc.NOT_RUN
    if opts.dry_run:
        _print_artifacts_dry_run(repo_root, opts)
        return Rc.OK
    return _run_artifacts(repo_root, opts)


def native_extract_main(repo_root: Path, argv: list[str]) -> int:
    """The module's entry point — reachable via the CLI subcommand AND a direct import.

    Parked 2026-08-24, unparked 2026-08-26 (`cli.py::_run`, `mise.toml:711`) —
    see the module docstring for that history and for #479/#480/#481, the
    three confirmed defects a caller of EITHER path was accepting while the
    CLI subcommand was closed and the only way in was a direct import.
    """
    try:
        opts = _parse(repo_root, argv)
    except _UsageError as exc:
        print(
            f"[graphify-native-extract] {exc}. Accepted argv: "
            "[--out DIR] [--target DIR] [--token-budget N] [--max-concurrency N] "
            "[--model NAME] [--backend NAME] [--allow-parallel-claude-cli] [--cluster] "
            "[--artifacts [VIEW...]] [--dry-run]"
        )
        return Rc.BAD_REQUEST

    out_problem = _refuse_out(repo_root, opts)
    if out_problem:
        events.fail("graphify_native_extract.unsafe_out", out_problem)
        return Rc.BAD_REQUEST

    # Before the dry-run too, deliberately: a preview that renders a plan for a
    # backend the installed graphify does not have is a preview of a run that
    # cannot happen, and the point of a dry run is to find that out cheaply.
    backend_problem = _refuse_backend(opts.backend)
    if backend_problem:
        events.fail("graphify_native_extract.unknown_backend", backend_problem)
        return Rc.BAD_REQUEST

    exe = graphify_exe(repo_root)
    if opts.cluster:
        return _dispatch_cluster(repo_root, exe, opts)
    if opts.artifacts:
        return _dispatch_artifacts(repo_root, opts)
    return _dispatch_extract(repo_root, exe, opts)
