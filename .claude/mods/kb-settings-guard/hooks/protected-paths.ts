// HAND-MAINTAINED TODAY; GENERATED LATER.
//
// Intended source of truth: `kb_setup.settings_guard.PROTECTED_SUFFIXES`.
// 🔴 NOT GENERATED YET. This header describes `kb-guard-codegen` and
// `kb-guard-codegen-check`, NEITHER OF WHICH EXISTS — ticket G02 (#755) builds
// them, and the schema becomes the authority generating both this file and the
// python classifier. Until then this list is maintained BY HAND and the drift
// gate it names is absent, which is exactly the 'generated output with no
// generator' failure mode the programme is meant to close.
//
// A `.json` file cannot be used here: the hooks-module loader compiles every
// import as TypeScript, so importing `./protected-paths.json` fails with
// `does not parse: Unexpected token (1:13)`. A relative `.ts` import works,
// which is why this file is TypeScript holding data.
//
// Ruled by Ray 2026-09-11 (grilling Q3): the settings pair PLUS the guard's own
// machinery, because a lane that can edit `mise.toml` neuters every `kb-*` guard
// task just as surely as one that edits `settings.json`.

export const PROTECTED_SUFFIXES: readonly string[] = [
  ".claude/settings.json",
  ".claude/settings.local.json",
  "mise.toml",
  "hk.pkl",
  "python/src/kb_setup/hook_guard.py",
];
