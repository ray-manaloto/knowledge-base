---
type: "query"
date: "2026-08-25T17:12:35.338217+00:00"
question: "Do currency.toml watch entries fire once written and reviewed?"
contributor: "graphify"
outcome: "corrected"
correction: "A written, reviewed watch item is not an active one. `codegen-tags-carry-no-v-prefix`\nwas a note about tag v-prefixes that could never fire — and in the SAME session\n`currency apply` wrote `hk = \"v1.56.1\"` into the mise pin (the GitHub tag where a\nbare version belongs), which `mise ls hk` reported as `(missing)`. That is #499:\nthe exact failure the dormant note describes.\n\nThe rule: a config parser that reads specific keys and IGNORES the rest converts\na typo into silence, and silence is indistinguishable from \"nothing to report\".\nBefore trusting that a config-driven check is live, prove it by asking the tool\nto ACT on the entry (here, `watch-reviewed --ref <id>`) rather than by reading\nthe file and seeing the entry present.\n\nSecond-order: copying an existing block as a template propagates its defects.\nI introduced a fifth dead entry by modelling on agnix's, which was itself dead.\n"
---

# Q: Do currency.toml watch entries fire once written and reviewed?

## Answer

No. `currency.toml`'s `[[tool.*.watch]]` entries are parsed by
`python/src/kb_setup/currency/config.py:362`, which reads `fields.get("ref")`.
FOUR entries spelled the key `id` and were silently dropped — never parsed,
never surfaced, never able to fire:

  agnix                    agnix-tags-are-annotated-and-unsorted
  datamodel-code-generator codegen-version-literal-is-load-bearing-in-a-test
  datamodel-code-generator codegen-tags-carry-no-v-prefix
  rumdl                    rumdl-tags-are-annotated  (added this session by
                           copying agnix's shape, reproducing the defect)

Control arm: `currency watch-reviewed --tool rumdl --ref ...` returned
`local refs: none` with the `id` spelling and recorded successfully after the
rename, so the probe discriminates.


## Outcome

- Signal: corrected
- Correction: A written, reviewed watch item is not an active one. `codegen-tags-carry-no-v-prefix`
was a note about tag v-prefixes that could never fire — and in the SAME session
`currency apply` wrote `hk = "v1.56.1"` into the mise pin (the GitHub tag where a
bare version belongs), which `mise ls hk` reported as `(missing)`. That is #499:
the exact failure the dormant note describes.

The rule: a config parser that reads specific keys and IGNORES the rest converts
a typo into silence, and silence is indistinguishable from "nothing to report".
Before trusting that a config-driven check is live, prove it by asking the tool
to ACT on the entry (here, `watch-reviewed --ref <id>`) rather than by reading
the file and seeing the entry present.

Second-order: copying an existing block as a template propagates its defects.
I introduced a fifth dead entry by modelling on agnix's, which was itself dead.
