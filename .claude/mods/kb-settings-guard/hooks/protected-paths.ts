// GENERATED — do not edit by hand.
//
// Source of truth: `kb_setup.settings_guard.PROTECTED_SUFFIXES`.
// Regenerate with `mise run kb-guard-codegen`; `mise run kb-guard-codegen-check`
// is the drift gate. Hand edits are reverted by the next regeneration and fail
// the gate in the meantime.
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
