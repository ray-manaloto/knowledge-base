---
type: "query"
date: "2026-08-17T22:19:06.863396+00:00"
question: "Does a subscription-minted CLAUDE_CODE_OAUTH_TOKEN authorize the developer Models API?"
contributor: "graphify"
outcome: "corrected"
correction: "A 401 cannot tell you WHICH of two things is wrong, and my control arm could\nnot either.\n\nI probed `GET /v1/models` with a subscription-minted `CLAUDE_CODE_OAUTH_TOKEN`\nand got 401 for a real model AND 401 for a bogus model id. I read that as\n\"auth is checked before existence, therefore this credential TYPE is not\nauthorized for the developer API\" and reported it as settled — a permanent\nfinding that closed a question the direction doc had flagged as the crux.\n\nIt was wrong. The token had a typo. After Ray corrected it in Doppler and I\nre-synced, the identical probe returned **200 for the real model and 404 for\nthe bogus one**.\n\nThe trap is precise: a MALFORMED credential and an UNAUTHORIZED credential are\nindistinguishable from outside, because both fail at the same layer. My control\narm (bogus id) discriminated \"path\" from \"auth\" — which was a real distinction\n— but said nothing about WHICH auth failure it was. I treated an arm that\ndiscriminated one axis as if it had discriminated the axis I was reporting on.\n\nThe rule: before concluding a credential TYPE is unauthorized, prove the\ncredential itself is well-formed — the 404 on a bogus id under a working\ncredential is the only evidence that separates the two. An all-401 result is\n\"could not authenticate\", never \"this kind of credential cannot reach here\".\n"
---

# Q: Does a subscription-minted CLAUDE_CODE_OAUTH_TOKEN authorize the developer Models API?

## Answer

# Round outcome — 2026-08-17 (f)

## Shipped
`7c538e03` on `feat-model-limits-resolver`: `kb_setup.model_limits` +
`mise run kb-model-limits`. Resolves a model's output ceiling in order —
Models API via the official `anthropic` SDK -> docs `.md` -> committed
`docs/model-limits/snapshot.json` -> **raise**. No literal fallback.
27 tests, `kb-check` green on all four checks.

Live, `source=models-api`: opus-5 / sonnet-5 / fable-5 max_output 128000,
haiku-4-5 64000; max_input 1M / 1M / 1M / 200K; haiku resolves to the dated
`claude-haiku-4-5-20251001`. `anthropic>=0.122.0` is now a declared dependency.

## Facts established
- `claude setup-token` works on a Max subscription and its token **does**
  authorize `GET /v1/models` (200 real / 404 bogus).
- The docs `.md` route is credential-free and works, but its table is
  TRANSPOSED and the parse is column-positional.
- Two ship gates are red for reasons predating this round, both control-armed
  by stashing every local change: the corpus authority digest for
  `manifest.json`, and `typos` finding 430 errors in
  `sources/extractions/agent-harness-docs-docs.json` (corpus content).
- graphify 0.9.46 investigated: all three local watch items re-probed,
  `moved: []`, nothing in it unblocks the parked work.


## Outcome

- Signal: corrected
- Correction: A 401 cannot tell you WHICH of two things is wrong, and my control arm could
not either.

I probed `GET /v1/models` with a subscription-minted `CLAUDE_CODE_OAUTH_TOKEN`
and got 401 for a real model AND 401 for a bogus model id. I read that as
"auth is checked before existence, therefore this credential TYPE is not
authorized for the developer API" and reported it as settled — a permanent
finding that closed a question the direction doc had flagged as the crux.

It was wrong. The token had a typo. After Ray corrected it in Doppler and I
re-synced, the identical probe returned **200 for the real model and 404 for
the bogus one**.

The trap is precise: a MALFORMED credential and an UNAUTHORIZED credential are
indistinguishable from outside, because both fail at the same layer. My control
arm (bogus id) discriminated "path" from "auth" — which was a real distinction
— but said nothing about WHICH auth failure it was. I treated an arm that
discriminated one axis as if it had discriminated the axis I was reporting on.

The rule: before concluding a credential TYPE is unauthorized, prove the
credential itself is well-formed — the 404 on a bogus id under a working
credential is the only evidence that separates the two. An all-401 result is
"could not authenticate", never "this kind of credential cannot reach here".
