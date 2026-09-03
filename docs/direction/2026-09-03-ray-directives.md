# Ray's directives — 2026-09-03

VERBATIM. This file is the standing brief a round is measured against; do not
paraphrase, and do not "tidy" the wording. Session `kb-20260902.004`.

## 1. Subscription only — CLI only, no API keys, either vendor

> we only have a chatgpt/codex subscription plan (so only cli)
> we cant use or have access to anything that requires an api key
> the same for claude

**Scope this widens:** `do-not.md` #4 already forbids a key-detected LLM backend
for the corpus. This is broader — it is about what the project may DEPEND on at
all. Anything reachable only through a metered API is out of reach, for codex and
for Claude. It is also why `codex_lane`'s guarded set is scoped to CLI
subcommands: guarding one we cannot run costs nothing, missing one we can is the
failure the guard exists to stop.

## 2. Keep the hosted graphify MCP; ours is `kb`

> i think there is still confusion
> the app.graphify.com mcp provides more features we dont yet support
> so we should keep that
> and our code for the rest

> can we just name ours knowledge-graph or kb for short

Ruled after a swap that removed hosted from both clients — **that swap was
wrong** and was reverted in `91e7186e`. Hosted stays as `graphify`; the local
stdio server is registered as **`kb`**. Sharing one name is not a style question:
it broke codex outright (`url is not supported for stdio`).

## 3. `kb` is a BACKLOG, not a border — replicate the hosted surface

> we will be building more functionality to this knowledge-graph as we get
> through our backlog of issues

> and the codex lane(s) shoudl have found this, one of our goals is to be able
> to replicate the functionality the remote one does and its formal verification
> and other features

> open a pwf task plan items for this and all other items the codex lanes found
> that are not in the task plan

**The criticism lands on the lane's BRIEF, not only its output.** A capability
lane produced a correct 319-line gap table and framed every hosted-only row as a
permanent division of labour, because nothing it read said the gap was work to be
done. Tracked as **U-R0…U-R12** and **U-G1…U-G10** in the pwf plan.

## 4. Do not guess — the sources are local, and lanes are for research

> dont guess, we have access to the codex source code and other codex graphify
> sources as a graphify source
> and you can inspect 'codex --help' more
> or search github issues/prs/discussions
>
> run codex lanes to research

**Said after I wrote a design conclusion into a docstring from ONE CLI error
string** — that `codex review --base` and a custom prompt were mutually
exclusive, therefore the METHOD paragraph was undeliverable. The pinned codex
source sits at `sources/codex/` at the exact version we run. A lane read the clap
definitions and found `-c developer_instructions=…`, a global option outside the
conflict set, which delivers instructions with base selection after all.

The general form: **a CLI's help text and its error strings are secondary
artifacts. The argument definitions are primary, and we have them.**

## 5. Try `codex review`, and get this branch reviewed

> lets just get what we have reviewed
> can we try out the 'codex review' cli now?

Both done. `codex review` found **6** findings on its own instructions and **7,
six of them P1, every one executed** once the METHOD paragraph was delivered
through `-c developer_instructions`. It is a viable `kb-review` cold lane; #672
U2's stated risk is resolved rather than accepted.

## See also

- `docs/direction/2026-08-28-ray-directives.md` — the previous brief.
- `#672` — Phase U, which every directive here shapes.
- `docs/setup-inventory.md` — the observed-vs-configured record these produced.
