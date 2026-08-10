---
type: "query"
date: "2026-08-06T20:06:56.337677+00:00"
question: "Does kb-currency-check cover every pinned tool?"
contributor: "graphify"
outcome: "corrected"
correction: "currency.toml is a JUDGMENT layer, not a coverage layer, and treating it as coverage left half the toolchain drifting silently: it declared 7 tools while mise.toml pins 14, and step 1 printed nothing about the other 7. Worse, an INSTALLED-VERSION MEASUREMENT IS ONLY A CLAIM ABOUT THAT VERSION — agnix was pinned 0.40.0 against a latest of 0.46.0, and v0.44.0 had ALREADY fixed the CC-AG-003 rejection of documented model values including `fable`, so an upstream issue was filed against a defect whose fix had shipped two releases earlier and then closed with a correction. The control arms were sound; the premise was not. Same-day sweep of the untracked pins: uv 0.11.28->0.12.2, rumdl v0.2.40->v0.2.52, typos 1.48.0->1.49.0, pkl 0.32.0->0.32.1 genuinely behind — while codex only LOOKED behind because the probe took the newest tag including an -alpha, and a prerelease is not drift. Ruling: Renovate covers all 14; currency.toml tracks all 14 with judgment DEPTH only where being wrong is expensive. Port spec is #204, which also corrects the premise that dotfiles runs a Renovate CI job — it runs the Mend-hosted app plus a local dry-run task, and of its 8 customManagers exactly one ports."
---

# Q: Does kb-currency-check cover every pinned tool?

## Answer

No -- currency.toml declares 7 tools while mise.toml [tools] pins 14, so the
untracked half drifts with step 1 printing nothing. agnix was pinned 0.40.0
against a latest of 0.46.0, and v0.44.0 had ALREADY fixed the CC-AG-003
rejection of documented model values including `fable` -- so an upstream issue
was filed against a defect whose fix had shipped two releases earlier, then
closed with a correction. The control arms were sound; the premise was not. An
installed-version measurement is only a claim about that version.

Sweep of the untracked pins the same day: uv 0.11.28 -> 0.12.2, rumdl v0.2.40 ->
v0.2.52, typos 1.48.0 -> 1.49.0, pkl 0.32.0 -> 0.32.1 all genuinely behind. codex
looked behind and was NOT -- the probe took the newest tag including an -alpha,
and a prerelease is not drift.

tool-currency-and-native-first.md already states the division: "Renovate still
owns routine bumps. This skill is the judgment layer." Nothing is currently the
coverage layer. Ruling: Renovate covers all 14; currency.toml tracks all 14 with
judgment DEPTH only where being wrong is expensive. Port spec is #204, which
corrects the premise that dotfiles has a Renovate CI job -- it does not, it runs
the Mend-hosted app plus a local dry-run task, and of its 8 customManagers
exactly one (hk.pkl schema) ports.

## Outcome

- Signal: corrected
- Correction: currency.toml is a JUDGMENT layer, not a coverage layer — it declared 7 tools while mise.toml pins 14, so the untracked half drifted with step 1 printing nothing. And an installed-version measurement is only a claim about THAT VERSION: agnix's CC-AG-003 defect had been fixed two releases before the issue was filed against it. The control arms were sound; the premise was not. Ruling: Renovate covers all 14; currency.toml tracks all 14 with judgment depth only where being wrong is expensive (#204).