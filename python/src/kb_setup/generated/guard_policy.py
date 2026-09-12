# Copyright (c) 2026 Raymond Manaloto
"""Generated guard-policy enum; edit the schema and rerun the generator."""

from enum import Enum


class ProtectedPathSuffix(Enum):
    """A path a delegated lane may never write: it switches off this repo's own guard stack.

    Ruled by Ray, 2026-09-11 (grilling Q3): the settings pair plus the guard's own machinery,
    because a lane that can edit `mise.toml` neuters every `kb-*` guard task just as surely as
    one that edits `settings.json`. This is the ONE authority two consumers are generated from:
    the TypeScript array `.claude/mods/kb-settings-guard/hooks/protected-paths.ts` imports
    (`PROTECTED_SUFFIXES`), and the Python enum `kb_setup.settings_guard` re-exports under the
    same name. Regenerate both with `mise run kb-guard-codegen`; `mise run kb-guard-codegen-
    check` is the drift gate. A value here is matched as an exact path, or as a `/`-prefixed
    suffix of a backslash-to-forward-slash normalised path — see `isProtectedPath` in
    `register.ts` and `is_protected_path` in `settings_guard.py`, which must stay semantically
    identical. This schema, its own generator, and its own Python consumer are themselves in the
    enum below — so once the settings-guard mod is registered (G04, #757), editing this policy
    from a delegated lane in the main checkout is denied like every other entry here; that edit
    happens in a worktree, where a lane already has full authority.
    """

    field_claude_settings_json = ".claude/settings.json"
    field_claude_settings_local_json = ".claude/settings.local.json"
    mise_toml = "mise.toml"
    hk_pkl = "hk.pkl"
    python_src_kb_setup_hook_guard_py = "python/src/kb_setup/hook_guard.py"
    schemas_guard_policy_schema_json = "schemas/guard-policy.schema.json"
    python_src_kb_setup_guard_codegen_py = "python/src/kb_setup/guard_codegen.py"
    python_src_kb_setup_settings_guard_py = "python/src/kb_setup/settings_guard.py"
    field_claude_mods_kb_settings_guard_hooks_protected_paths_ts = (
        ".claude/mods/kb-settings-guard/hooks/protected-paths.ts"
    )
