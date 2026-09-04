# Probe failures — the worked examples behind the control-arm rule

Moved out of `.claude/rules/probes-need-a-control-arm.md` on 2026-09-03 (#697),
which was at exactly its 200-line ceiling. The rule keeps every norm and every
lesson; what moved here is the narrative evidence for two of them. Same split the
rule already applies to arming your own fixes, where the procedure lives in the
`kb-review` skill and the rule holds only the norm.

## Inherited numbers

### The model bake-off that had to be discarded

A session inherited a 5-row model bake-off table and reported it as "same corpus,
same flags, so it is comparable". Only the corpus was ever constant: graphify
records **no backend or model in any artifact**, the semantic cache key is
model-blind, and every arm was n=1. The whole comparison had to be discarded —
after a claim from it had already been reported as a finding.

### Two numbers invalidated by the commit that wrote them

One branch shipped both:

- *"45 tasks listed vs 41 declared"*, in a commit that **added a task**.
- *"82 files in `docs/`"*, in a commit that **added a doc**.

Both were correctly measured. Both were wrong on arrival. Neither was noticed
until a reviewer re-ran the count. The author *did* measure, which is exactly why
the figure reads as verified forever.

## Unreachable by construction

A guard here was documented as dead on a chain of true premises:

1. a `file:line` token ends in `:<digits>`,
2. so its extension contains a `:`,
3. every allowlisted extension is short and alphanumeric,
4. therefore none is one edit away.

Every premise true, conclusion false. The chain never asked whether an
allowlisted extension **ends in a digit**. `mp3` does — so `foo.mp:3` repaired to
`foo.mp3`, and the guard was live all along.

The arm that should have caught it was labelled `EXPECTED NO-OP` in the harness,
so two runs *confirmed the prediction* instead of testing it. It had only
survived because the test's fixtures could not exhibit the harm — the rule's
"bound" failure wearing a different hat.

## See also

- `.claude/rules/probes-need-a-control-arm.md` — the norms these support.
- `docs/invariant-provenance.md` — the same treatment applied to `do-not.md`.
- `docs/currency/design-notes.md` — and to `CLAUDE.md`'s currency section.

## GitHub repos touched

_None._ Every line above was moved verbatim from this repo's own
`.claude/rules/probes-need-a-control-arm.md`.
