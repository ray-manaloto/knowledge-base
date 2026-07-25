# OMC Directory Conventions — RENAMED, see `agent-artifact-conventions.md`

**This rule moved to `.claude/rules/agent-artifact-conventions.md` on
2026-07-25.** The working tree it governed is now **`.agent/`**, not `.omc/`.

`.omc/` was named after the `oh-my-claudecode` plugin, which is not enabled in
either repo — a convention named for a tool nothing loads.

This stub exists only for one merge cycle. `parity.toml` in the sibling
dotfiles repo gates rule presence **by stem**, so deleting this file before
dotfiles has renamed its own copy and updated `parity.toml` would turn dotfiles
`main` red. The sequence is: this repo adds the new stem (here) → dotfiles
renames and repoints `parity.toml` → this repo deletes this stub. Parity stays
green at every merge point.

**Read `agent-artifact-conventions.md`. Nothing here is current.**
