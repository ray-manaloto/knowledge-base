# Currency run — antigravity-cli — 2026-09-10T08:06:44+00:00

**Verdict:** antigravity-cli 1.1.25 → 1.2.0: 2 question(s) for review

Related: [[tool-currency-log]] · [[antigravity-cli]]

## Step 1 — in sync?

Pinned `1.1.25` · resolved `1.2.0`

| check | status | detail |
|---|---|---|
| version | drift | agy on PATH is 1.2.0 but the reviewed version is 1.1.25 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have |
| manifest | drift | sources/antigravity-cli.manifest pins 1.1.25 but the running version is 1.2.0 — the corpus describes code we do not run |

## Steps 2-3 — upstream

- Latest (github): `1.2.0`
- GitHub release: `1.2.0`
- Reachable: yes

### Release notes

```text
## 1.1.26

- Added half-page scrolling with `Ctrl+D` and `Ctrl+U` to the artifact viewer.
- Added the `pickerGrouping` setting to `/config` and `settings.json` to configure the default conversation list view in `/resume` (flat or grouped by workspace).
- Improved terminal ASCII diagram rendering for Mermaid flowcharts in the artifact viewer and conversation.
- Improved `/logout` execution time by short-circuiting token removal directly to file storage when keyring storage is bypassed or unreachable.
- Changed unselected model families in the interactive `/model` picker to default to medium reasoning effort instead of low.
- Fixed subagent tasks unexpectedly prompting for tool approval in always-proceed mode while viewing the subagent details panel.
- Fixed orphaned Git worktrees accumulating on disk under `.system_generated/worktrees` when killing subagents or deleting conversations.
- Fixed SQLite database WAL checkpointing on CLI exit so trailing session metadata updates are flushed to disk before shutdown.
- Fixed customization discovery logging spurious errors when accessing temporary directories or paths outside the active workspace.

## 1.1.27

… (truncated)
```

### Features to consider adopting

_**Could not tell.** The release notes are non-empty but match no changelog format this scan understands (no `Added`/`Highlights` section, no `feat:` prefixes, no adoption phrases), so this is **not** a report of zero features — read the notes by hand._

## Step 4 — tracked issues and watch items

_No watch items configured for this tool._

## Step 5 — decision

Gates passed:

- ✅ versions are readable and move forward
- ✅ latest version has a readable GitHub release
- ✅ extras unchanged
- ✅ no tracked issue moved

### Gate: no breaking/removal/deprecation marker

**The release notes flag a breaking change. Adopt it anyway?**

- Detail: Markers found: deprecated.
- Recommended: Read the notes; plan a rebuild and a re-verify before adopting.
- **Answer:** _not yet answered_

### Gate: step 1 currently green

**The current install is already out of sync. Fix that before bumping?**

- Detail: version: agy on PATH is 1.2.0 but the reviewed version is 1.1.25 — it self-updated. Review the releases between them, then bump `expected` in currency.toml to record that you have; manifest: sources/antigravity-cli.manifest pins 1.1.25 but the running version is 1.2.0 — the corpus describes code we do not run
- Recommended: Resolve the drift first — bumping on top of an unknown state makes the result unattributable.
- **Answer:** _not yet answered_

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
