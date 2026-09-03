---
type: "query"
date: "2026-09-03T00:40:42.516531+00:00"
question: "Does ty's LSP work for this project, and do this repo's hooks actually run in codex lanes?"
contributor: "graphify"
outcome: "corrected"
correction: "I told Ray \"our guard stack already runs in every codex lane\" on the strength of\nreading `.codex/hooks.json` and confirming `Bash` is a canonical codex matcher.\nBoth facts were true and the conclusion was false: a non-managed codex hook is\nskipped until a human trusts it, and trust is recorded per hook HASH. The guard\nstack ran only because someone had trusted it once; the hook I committed that\nsame hour had zero trust entries and would never have fired.\n\nThe correction is not \"check trust\". It is that I reason from configuration files\nand call the result behaviour. Ray redirected me five times in one session and\nevery redirect found something a single live probe would have shown — including\nthis one, which he found by reading `codex --help` while I was writing tests\nagainst a payload I had invented from a docs page.\n\nRule for future rounds: no claim about a mechanism without the command that\nobserved it RUNNING. Configuration is a hypothesis.\n"
---

# Q: Does ty's LSP work for this project, and do this repo's hooks actually run in codex lanes?

## Answer

ty's language server was never broken. It starts ON DEMAND, so every `ps` probe
across three sessions looked for a lazily-created process before anything created
it. The live registrant is `astral@astral-sh`, which declares ty INLINE in
`plugin.json` as `lspServers` — a location no filename search for "lsp" can find.

What IS wrong is narrower and measurable:

1. `uvx ty@latest` has pulled 26 ty versions since 2026-03-27 and the pinned
   0.0.77 was never one of them (uv's own archive cache; 0.0.75 on Aug 26 ->
   0.0.78 today). Ray ruled always-newest is fine and the LAGGING PIN is the
   defect.
2. `currency` reports "auto-applying (6/6 gates)" for ty and ruff and then
   REFUSES to apply, because neither has a `mise_key` (`apply.py:177`). uv, which
   has one, really applies — the control arm.
3. Diagnostic delivery is bound to the Edit tool. A `perl -pi` edit gets NO ty
   diagnostic; the same error surfaces the instant an Edit-tool edit touches an
   unrelated line in that file. Proven three-armed.
4. A codex hook is SKIPPED until trusted, and trust is keyed to the hook's hash.
   Measured: 3 trusted `pre_tool_use` entries for this repo, 0 for
   `post_tool_use`. Two real lanes, one variable: with
   `--dangerously-bypass-hook-trust` the lane got the ty diagnostic; without it,
   "I received no feedback after the edit".


## Outcome

- Signal: corrected
- Correction: I told Ray "our guard stack already runs in every codex lane" on the strength of
reading `.codex/hooks.json` and confirming `Bash` is a canonical codex matcher.
Both facts were true and the conclusion was false: a non-managed codex hook is
skipped until a human trusts it, and trust is recorded per hook HASH. The guard
stack ran only because someone had trusted it once; the hook I committed that
same hour had zero trust entries and would never have fired.

The correction is not "check trust". It is that I reason from configuration files
and call the result behaviour. Ray redirected me five times in one session and
every redirect found something a single live probe would have shown — including
this one, which he found by reading `codex --help` while I was writing tests
against a payload I had invented from a docs page.

Rule for future rounds: no claim about a mechanism without the command that
observed it RUNNING. Configuration is a hypothesis.
