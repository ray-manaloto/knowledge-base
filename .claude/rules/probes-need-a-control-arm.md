# Probes Need a Control Arm: A Check That Can Only Pass Is Not a Check

Before you believe a probe's answer — especially a NEGATIVE one ("not found",
"doesn't exist", "it's dead", "no results") — prove the probe **can** produce
the other answer. Run it against a case you know succeeds, or a case you know
fails. A probe with no control arm is not evidence; it is a coin that only has
one face.

This applies to **every ad-hoc probe**: a `find`, a `curl`, a `grep`, a
`kb-query`, a liveness check, a shell one-liner. Those are where it actually
bites, because nothing reviews them.

## Why this rule exists

One session produced **five false negatives**, every one from a probe that
could not have succeeded:

| Probe | Said | Truth |
|---|---|---|
| `find … -maxdepth 4 -iname '*grill*'` | "it doesn't exist" | It exists at **depth 7**. |
| `find … -name 'agent-*.jsonl'` | "AGENT DEAD, no transcript" | Alive; transcripts are `<uuid>.jsonl`, so the glob **can never match**. ~10 min of work redone for nothing. |
| `curl …/resolute/` → 301 | (nothing — 301 for every input) | A redirect, not evidence. |
| PyPI loop with `jq -e '.info'` | "package NOT ON PYPI" | It is. The next query returned its metadata. |
| a heredoc compile check | "feature FAIL" | The heredoc quoting was broken; the feature was fine. |

Each one was cheap to disprove and expensive to believe.

The **inverse** bites too. `cmd | grep -q PAT` under `set -o pipefail` returns
**141**, so the check fails *because the match succeeded* — a probe that can
only fail.

## The graph is a probe too, and it has the same failure mode

`mise run kb-query -- "<question>"` returning nothing means one of:

1. the corpus genuinely lacks it;
2. the source was never ingested (no manifest, no extraction chunk);
3. it was ingested but the **query terms don't match the extracted node
   labels** — the single most common case, and indistinguishable from (1);
4. `graphify-out/graph.json` is stale or was built without that source.

**Control-arm every empty graph result** by querying a term you KNOW is in the
corpus with the same command shape. If that also returns nothing, the graph or
the query is broken — not the world. `mise run kb-currency-check` answers (4)
directly: it reports which graphify version actually built the graph, and a
rebuild that bypassed `kb-build` reports *version unknown* rather than a false
green.

**"Extraction ran" is not "extraction captured it."** A chunk that merges
cleanly can still be near-empty; `mise run kb-validate-chunks` is the arm.

## Cross-check: when two probes disagree, one of them is broken

The cheapest bug detector available is a **second probe of the same fact by a
different route**. It needs no fixture: if two probes of one fact disagree, you
have found a defect *for free* — and it is in a probe far more often than in
the world. Reach for this the moment a result surprises you, before you write
up the surprise.

| the probe said | the disagreeing route | what was actually broken |
|---|---|---|
| a version pin FAILS to install | the same pin in a **clean container** → fine | the environment was dirty, not the pin |
| a CI job SKIPPED ⇒ "unaffected" | reading the job's `if:` condition | a SKIPPED job **never asked the question** |
| every package reports MISSING | the same command without the outer quoting | the inner shell ate the variable |
| graphify **issue #959 is OPEN** ⇒ "custom OpenAI endpoints are blocked" | reading the **installed** `llm.py` | the feature shipped in 0.8.40; the issue is stale-open |
| a plugin says *"Discord's search API isn't exposed to bots"* (in 3 places) | reading **Discord's own** API docs | the endpoint was documented **two days after** the plugin's first commit |

**Source beats issue tracker. A tool's claim about a platform ages.** Both of
the last two rows are the same shape: a *secondary* artifact (an unclosed
issue, a dependency's README) was read as the current state of a *primary* one
(the shipped source, the platform's API). Issues stay open after the fix lands;
vendored docs freeze at their commit date. When a secondary source says
"impossible" and it matters, **go read the code or the owner's docs**.

That row is not hypothetical here — graphify is this repo's core dependency and
its issue tracker is the thing most likely to be quoted at you.

## Rules

1. **Arm the negative.** Before reporting "X does not exist", run the same probe
   against something that **does** exist. If it can't find that either, your
   probe is broken, not the world.
2. **Arm the positive.** Before reporting "the gate works", reintroduce the bug
   and confirm it **fails**. A gate verified only on clean code is decoration.

   **Reintroduce the bug REALISTICALLY.** A mutation that isn't the real
   failure proves nothing. Renaming `def foo` → `def foo_REMOVED` leaves the
   original as a *substring*, so a substring check still passes — the probe was
   the no-op, not the gate. Two lessons, the second being the expensive one:
   a mutation must actually *destroy* what the check looks for, and it must be
   a break that could **really happen**. Deleting the line that CALLS a
   function is usually the realistic break; renaming its definition is not.
3. **Bound-limited searches are suspect by construction.** `-maxdepth`,
   `head -N`, `--limit`, a time window, a `2>/dev/null`: each can turn "absent"
   into "unreachable". Either remove the bound or prove the target is inside it.

   **Display bounds count too** — `ls … | tail -15` is a bound, and so is
   checking N exact paths instead of asking "does it exist anywhere". A
   relative time bound can be silently invalid: `find … -newermt "-20 minutes"`
   returns nothing on macOS/BSD `find`, indistinguishable from "no recent
   files".

   **A TOKEN SPELLING is a bound too — the most common form.** A session
   grepped `lmstudio` and `lm_studio`, got 0, and reported *"graphify supports
   NONE of MLX / LM Studio / Jan"*. graphify spells it **`LM Studio`, with a
   space** — 3 hits, one in its own `--help`. The literal grep was true; the
   conclusion was backwards.

   The habit that catches every one: **a 0-result grep is not an answer until a
   control arm has run.** Grep a term you KNOW is present in the same corpus
   with the same command shape first.
4. **A redirect/timeout/parse-error is not a "no".** HTTP 301/000, a `jq` miss,
   an empty `grep` — distinguish "answered no" from "never asked".
5. **Say which arm you ran.** When reporting a probe result, state the control:
   "bogus-input → 404 while known-good → 200, so the probe discriminates." A
   result without its control is an opinion.
6. **An INHERITED number is not a measurement — re-derive it or label it.** A
   figure that arrives from a handoff or a prior session's table has *no
   control arm attached*. Repeating it converts someone else's unverified note
   into your finding.

   A session inherited a 5-row model bake-off table and reported it as "same
   corpus, same flags, so it is comparable". Only the corpus was ever constant:
   graphify records **no backend or model in any artifact**, the semantic cache
   key is model-blind, and every arm was n=1. The whole comparison had to be
   discarded — after a claim from it had already been reported as a finding.
   Before repeating an inherited number, either re-derive it and say so, or
   mark it explicitly as unverified. And when a number *ranks* things, ask what
   the **noise floor** is: a difference smaller than same-input variance is not
   a difference.
   **A number can be invalidated by the very commit that writes it.** Ask what
   would move a figure before you commit it, and if the answer is "this change",
   state the durable fact instead — the delta, the ratio, the mechanism. One
   branch shipped two: "45 tasks listed vs 41 declared" in a commit that ADDED a
   task, and "82 files in `docs/`" in a commit that added a doc. Both were
   correctly measured, both were wrong on arrival, and neither was noticed
   until a reviewer re-ran the count. This is the inherited-number failure with
   a shorter fuse: the author *did* measure, so it reads as verified forever.
7. **Cross-check a surprise before you report it.** A second route to the same
   fact costs seconds and settles which side is broken. Disagreement is a
   finding, not noise — and the finding is usually your probe.
8. **A generated table drifts from its generator — verify, don't copy.** An
   evidence table transcribed by hand (or built by a regex over the generator's
   source) is a probe with no control arm. One built this way silently dropped a
   row and attached two labels to the wrong rows. If a document carries a table
   produced by a script, re-derive it from the script's own data structure and
   assert the two agree; that check costs one command and is the only thing standing between a
   reader and a confident wrong number.

## Applies to

Every probe whose answer you act on or report: shell one-liners, `find`/`grep`
sweeps, `kb-query` results, HTTP checks, agent-liveness checks, and the FAIL
direction of every gate added to `hk.pkl`.

## See also

- `verify-before-advancing.md` — evidence discipline: read the real `rc`,
  never a piped tail.
- `md-size-budgets.md` — the worked example: a control-armed probe whose
  *report* dropped its bound.
