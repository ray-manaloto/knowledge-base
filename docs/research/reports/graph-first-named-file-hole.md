# `graph_first` has a measurable named-file hole — analysis and proposal

**Analysis only. `python/src/kb_setup/graph_first.py` is unchanged by this
report; no behaviour changed.**

Commit read: `2b1cdc3a04e70ba8a000e7a36157b15117fbe4cc` (worktree cut from the
caller's branch tip). Files read in full:
`python/src/kb_setup/graph_first.py`, `python/src/kb_setup/hook_guard.py`
(the `_graph_first` wiring), `tests/test_graph_first.py`,
`python/src/kb_setup/session_reflect.py`.

---

## 1. The trigger

Ray's own motivating observation (not independently reproducible from an
artifact, and reported here as such): an evening was spent re-researching a
topic this corpus already answered, entirely through `Read` calls and
single-file `Grep` calls — the `graph_first` guard never fired once, because
none of those calls is the thing it deny. This report builds the actual
measurement and a proposal, per the dispatching spec.

## 2. How the guard classifies a `Read` and a single-file search — cited

**`Read` is not evaluated at all.** `decide()`'s dispatch is:

```
python/src/kb_setup/graph_first.py:447-452
    if queried:
        return None
    if tool_name == "Grep":
        return _decide_grep(tool_input, cwd)
    if tool_name != "Bash":
        return None
```

Any `tool_name` other than `"Bash"` or `"Grep"` falls through the second
`if` and returns `None` unconditionally — there is no branch that inspects a
`Read` call's `file_path` at all. This is by design, stated in the module
docstring:

> `graph_first.py:26-28`: "DENY a Grep/rg with no file path (directory- or
> repo-wide) until a graph query has run this session; ALLOW Read of a named
> file and Grep scoped to one file."
>
> `graph_first.py:32`: "The target is **orientation**, which is the job the
> graph replaces. Reading a named file to change a specific line is not
> orientation and stays unblocked."

The refusal text itself repeats the same carve-out to the caller directly:

> `graph_first.py:107-108`: "Not denied: `Read` of a named file, a search
> scoped to ONE file, and any search of prose, logs or /tmp."

`tests/test_graph_first.py:156-158` (`test_read_of_a_named_file_is_never_denied`)
and `:276-283` (`test_the_hook_still_ignores_tools_it_does_not_guard`, the
end-to-end wired-hook version) both encode this as an **acceptance
criterion**, not an oversight.

**A single-file `Grep` is allowed by `_is_single_file`/`_is_prose_target`.**
`_decide_grep` (`graph_first.py:416-435`) denies only when `path` is absent,
or present but neither a single existing file nor a prose target:

```
python/src/kb_setup/graph_first.py:428-433
    if (
        isinstance(path, str)
        and path
        and (_is_single_file(path, cwd) or _is_prose_target(path, cwd))
    ):
        return None
```

`_is_single_file` (`:350-374`) requires the path to **exist** as a file —
this is itself the fix for a prior regression the module's own docstring
records (`:45-53`): a non-existent path used to count as "one file" on the
module's general "ambiguity resolves to ALLOW" principle, and composed with
`_looks_like_a_path`'s own ambiguity to let `rg 'src/utils'` — a repo-wide
search whose *pattern* merely contained a slash — sail through as a
false-negative (the round-2 P1). The module has already been wrong once in
this exact neighbourhood.

**The `Bash` path has a second, wider gap beyond named-file reads.**
`_searches_the_tree` (`:377-400`) only denies when the head command is a
recognised tree searcher — `rg`/`ag`/`ack`/`ripgrep`, `git grep`, or `grep`
with `-r`/`-R`. A plain, **non-recursive** `grep pattern file1 file2 …`
never reaches the path check at all:

```
python/src/kb_setup/graph_first.py:391-395
    recursive = (
        any(_GREP_RECURSIVE.match(w) for w in rest) if head == "grep" else head in _TREE_SEARCHERS
    )
    if not recursive or _restricted_to_prose(words):
        return None
```

`not recursive` short-circuits before `_paths_of`/`_is_single_file` ever
run — so this is not "many single-file allowances chained," it is a command
the guard has **no opinion about at all**, regardless of how many files it
names. `cat`, `head`, `sed -n`, `find`, `ls -R`, `fd`, `tree` are in the same
position: none is in `_TREE_SEARCHERS` and none is `grep`/`git grep`, so
`decide()` never routes them through `_searches_the_tree`'s deny branch
either. `ALLOW_COMMANDS` in the test suite already documents `grep -n
"decide" python/src/kb_setup/hook_guard.py # not recursive at all` (line 49)
and `ls -la # Not searchers at all` (line 88) as intended behaviour, not
oversights — this report is not disputing that scope, only naming its full
width.

## 3. The measurable shape of the hole

Ray's anecdote is unarmed by construction (a session's past behaviour cannot
be re-run), so the arm here is a direct call into the real `decide()`
against the real repo tree, holding `queried=False` fixed throughout — the
worst case, i.e. a session that has never run a graph query. Script (not
committed; reproducible from any checkout at this commit):

```python
import sys
from pathlib import Path
sys.path.insert(0, "python/src")
from kb_setup import graph_first

root = Path(".").resolve()
py_files = sorted(root.glob("python/src/kb_setup/*.py"))

# 1) Read every source file in the module, one call each.
denied = sum(
    1 for f in py_files
    if graph_first.decide("Read", {"file_path": str(f.relative_to(root))}, root, queried=False)
)

# 2) Grep every source file, one call each, one file at a time.
denied_grep = sum(
    1 for f in py_files
    if graph_first.decide(
        "Grep", {"pattern": "def ", "path": str(f.relative_to(root))}, root, queried=False
    )
)

# 3) ONE non-recursive Bash `grep` naming every file explicitly.
all_rel = " ".join(str(f.relative_to(root)) for f in py_files)
reason = graph_first.decide("Bash", {"command": f'grep -n "def " {all_rel}'}, root, queried=False)
```

Run against this commit's `python/src/kb_setup/` (75 files):

```
Enumerated 75 source files directly (no guarded search used: Path.glob() is
not a Bash/Grep tool call, so `decide()` never sees it).
Read tool over ALL 75 files, queried=False throughout: 0 denied
Grep tool, one file at a time, over ALL 75 files, queried=False throughout: 0 denied
ONE non-recursive `grep` Bash call naming all 75 files as explicit
arguments: ALLOWED
has_queried after all of the above: False
```

So the reproducible shape is: **an agent can read or grep the entire
tracked source tree of this repository, file by file, in a single session,
and never trip `graph_first`, and the session's `.queried` marker never
gets set by any of it** (`note_query` only fires on `Bash` commands matching
`_GRAPH_QUERY`, `hook_guard.py:441-445` — a `Read`, a `Grep`, or a
non-recursive `grep`/`cat` never earns or needs the unblock).

Two things make this a *hole* rather than merely "the documented carve-out
working as designed":

1. **The guard is entirely per-call and stateless except for one boolean.**
   `decide()` takes `queried: bool` and nothing else — there is no counter
   of how many distinct files a session has already read, no notion of
   breadth (how many directories), no session-scoped memory of "orientation
   already performed by other means." A first single-file `Read` and a
   71st single-file `Read` in the same session are graded identically.
2. **Discovery of *which* files to read is itself unguarded.** `find`,
   `ls -R`, and every non-recursive `grep`/`cat` are outside
   `_TREE_SEARCHERS` by design (§2), so an agent can enumerate the entire
   tree's file list without tripping the guard, then walk it one `Read` at
   a time. The two allowances compose into a full repo walk with zero
   guarded operations anywhere in the sequence.

This is not a parsing bug in the sense the module's docstring already
catalogues (`rg --sort path`, `rg -g '!*.md'`, `rg 'src/utils'` — all
*mis-classifications* of a single command). It is a **structural gap**: the
mechanism the guard has for "has this session already oriented itself" is
binary and keyed to one literal command family, while the behaviour it is
trying to discourage (aimless multi-file research standing in for one graph
query) is a *pattern across many individually-legitimate calls*, which a
stateless per-call `decide()` cannot see by construction — it would need to
observe the session's call history, not one call in isolation.

## 4. Candidate designs

### Option A — a per-session counter/budget on distinct single-file reads

Track distinct file paths read via `Read`/`Grep`/non-recursive `grep`
(dedup by path) in a marker file next to `.agent/state/graph-first/`, and
deny once a threshold (e.g. 5, or N-files-in-one-directory) is exceeded
without an intervening graph query.

**False-positive cost:** this directly re-criminalises the case the module's
own docstring names as the reason `Read` is exempt in the first place —
"Reading a named file to change a specific line is not orientation"
(`:32-33`). A legitimate multi-file debugging session (trace a call chain
across 8–10 files, fix a cross-cutting rename touching a dozen callers) is
*exactly* this shape and would trip the counter. `probes-need-a-control-arm.md`
rule 9 requires an "unreachable by construction" claim to be armed by
constructing the reaching case — the reaching case for a false positive here
is not hypothetical, it is the module's stated protected use.

There is also compounding risk specific to this module: two of its three
prior defects (`:45-53`, the round-1 and round-2 P1s) came from adding
shape-based judgment on top of an already-defensible rule and having the
combination resolve to the least-safe answer. A counter is a third piece of
shape-based judgment layered on the same classifier family.

### Option B — a breadth heuristic (N distinct directories, not raw count)

Deny once reads span more than M distinct top-level directories under
`python/src/kb_setup/`/`docs/`/etc. without a graph query, on the theory that
breadth (not depth) is what characterises "walking the whole corpus" versus
"working one bug."

**False-positive cost:** worse than Option A on the same axis. A
cross-cutting fix (rename a function called from five different modules,
follow one bug through `cli.py` → `hook_guard.py` → `graph_first.py` →
`session_reflect.py`) is high-breadth **and** exactly the "targeted work"
case Ray's scope protects. Breadth heuristics are also harder to get right
than a raw count and land in the same "shape, not position" trap this
module's docstring already flags as its own failure history.

### Option C — leave `decide()` alone; the discipline already exists elsewhere, make it load-bearing

`python/src/kb_setup/session_reflect.py` already computes exactly the ratio
this hole describes, per session, from the transcript, after the fact:

```
python/src/kb_setup/session_reflect.py:449-450
    _GRAPHIFY = re.compile(r"\bgraphify (?:query|explain|path|god-nodes)\b|\bkb-query\b")
    _SOURCE_READ = re.compile(r"\.(?:py|pkl|toml|js|ts)$")

python/src/kb_setup/session_reflect.py:678-681
    report.graph_skipped += sum(
        1
        for name, payload in tool_uses(path)
        if name in {"Read", "Grep"} and _reads_source(payload)
    )

python/src/kb_setup/session_reflect.py:799-800
    f"- {report.graph_queries} graphify/kb-query call(s) against "
    f"{report.graph_skipped} direct source read(s)"
```

This is the same measurement that originally justified building
`graph_first.py` at all — the module's own docstring opens with "one
session ran **0 graphify/kb-query calls against 19 direct source reads**"
(`:4-7`), which is `session_reflect`'s ratio, reported after the session
that motivated the guard's construction. `kb-session-reflect` is
`reflect_main`'s task, documented as "always 0; this reports, it never
gates" (`session_reflect.py:810-811`) and is wired as a step of
`/clear-prep` per its skill description, i.e. reviewed at a defined
checkpoint rather than nagged on every call.

**Why this is not just "leave it broken":** the spec's own instruction to
justify escaping the "warning = 0% compliance" finding applies here, and the
honest answer is that this is a **different kind of warning** than the one
that scored 0/19. The 0/19 warning fired inline on every single tool call,
mid-task, to the same agent that was incentivised to keep working — the
`graphify` hook context reminder printed "MANDATORY … you must run graphify
query" on nearly every call and was ignored every time, because acting on it
cost the in-flight task momentum. `session_reflect`'s ratio is not printed
per call; it surfaces once, at a natural stopping point
(`kb-session-reflect`/`/clear-prep`), to a reader who is not mid-task and
whose job at that point *is* to look at exactly this kind of ratio. That is
closer in kind to the `no_lint_skip`/`hk` gates (checked at a checkpoint,
not nagged inline) than to the graphify hook's inline warning — though it is
still unproven for this *specific* pattern, which is the honest caveat: no
measurement yet exists of whether a large `graph_skipped`/`graph_queries`
ratio actually gets acted on when a session/reviewer reads it.

**Known gap in the existing measurement, worth naming rather than silently
inheriting:** `_reads_source` (`:551-563`) counts *every* `Read`/`Grep` of a
source-extension target, with no distinction between a legitimately
single-file targeted read and one that is part of a de-facto tree walk — so
the ratio can be noisy in the other direction (a large `graph_skipped` from
one long, legitimate multi-file bugfix looks identical to an evening of
unfocused re-research). It also does not count `Bash`-level `cat`/
non-recursive-`grep` reads of source files at all (`tool_uses(path)` is
filtered to `name in {"Read", "Grep"}` only), so §3's demonstrated
non-recursive-`grep` gap is invisible to it too. A ratio that cannot tell the
two cases apart is evidence for a human/reviewing session to weigh, not a
number that could safely drive an auto-deny — which is itself an argument
for keeping this advisory rather than promoting it to a live gate.

## 5. Recommendation

**Option C: leave `graph_first.decide()` unchanged.** Reasoning:

1. Every measured defect in this guard family to date has been a **false
   positive**, never an evasion (`graph_first.py:37-39`,
   `a-guards-false-positives-are-text-about-the-guard`) — the base rate this
   module has actually produced argues against adding a fourth
   shape-based heuristic on top of a classifier that has already regressed
   twice from exactly that kind of addition (§4, Option A/B).
2. The failure mode described is structural — it needs session-scoped
   *history*, not a smarter per-call classifier. `session_reflect.py`
   already is that session-scoped mechanism, was already built for this
   exact ratio, and is already wired to a checkpoint
   (`kb-session-reflect`/`/clear-prep`) rather than an inline nag — so
   "put the discipline somewhere else" is not aspirational, it names a
   piece of code that already exists and already runs.
3. The one thing this report cannot yet claim is that the existing
   advisory report actually gets acted on for *this* pattern — that is
   unmeasured, not refuted. The honest next step, if this is worth pursuing
   further, is to watch a `graph_skipped`/`graph_queries` ratio in a live
   `kb-session-reflect` run against a session that exhibits the described
   evening-of-research shape, before considering anything that would change
   `decide()`'s behaviour.

This recommendation is a proposal only — the spec's Interfaces section
requires flagging that a change would be dissent-shaped, and no change is
made here.

## GitHub repos touched

_None._ This report reads only this repository's own source
(`python/src/kb_setup/graph_first.py`, `hook_guard.py`, `session_reflect.py`)
and its own test suite; no external repo, docs site, or issue tracker was
consulted.
