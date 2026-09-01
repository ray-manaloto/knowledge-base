# Currency run — antigravity-cli — 2026-09-01T18:16:55+00:00

**Verdict:** antigravity-cli 1.1.22 → 1.1.23: auto-applying (6/6 gates)

Related: [[tool-currency-log]] · [[antigravity-cli]]

## Step 1 — in sync?

Pinned `1.1.22` · resolved `1.1.22`

| check | status | detail |
|---|---|---|
| pin | ok | mise.toml pins antigravity-cli at 1.1.22 |
| resolution | ok | PATH reaches the pinned 1.1.22 |
| extras | skip | no extras declared for this tool |
| extra-probes | skip | no extra_probes declared for this tool |
| backend-probes | skip | no backend_probes declared for this tool |
| manifest | skip | this repo pins no source manifest for the tool |
| ref-binding | skip | this tool declares no revision bindings |
| skill-stamp | skip | this tool declares no skill version stamp |
| build-stamp | skip | this tool declares no build stamp |

## Steps 2-3 — upstream

- Latest (github): `1.1.23`
- GitHub release: `1.1.23`
- Reachable: yes

### Release notes

```text
## 1.1.23

- Improved `/model <name>` autocompletion to accept the proposed model name ghost text with `Tab`.
- Reduced subagent streaming overhead by sending subagent trajectory metadata once per subtrajectory instead of with every step.
- Fixed commands with subcommands (such as `models` or `agents`) hanging on an inherited, unclosed standard input pipe instead of executing immediately.
- Fixed CLI crashes caused by prompt hooks by catching hook panics and rejecting nil completion configurations in model requests.
- Fixed tool invocations and results omitting tool-call IDs when reconstructing request history for Gemini models.
- Fixed tool permission prompts for direct and MCP tool calls displaying generic prompt titles instead of their declared human-readable action descriptions.
- Fixed unconfigured or interrupted Google Cloud authentication and onboarding sessions dropping into broken chat sessions instead of prompting with the sign-in screen.
- Fixed transient authentication errors caused by token expiry clock skew by proactively refreshing browser and WIF OAuth tokens five minutes before expiration.

… (truncated)
```

### Features to consider adopting

_**Could not tell.** The release notes are non-empty but match no changelog format this scan understands (no `Added`/`Highlights` section, no `feat:` prefixes, no adoption phrases), so this is **not** a report of zero features — read the notes by hand._

## Step 4 — tracked issues and watch items

_No watch items configured for this tool._

## Step 5 — decision

Gates passed:

- ✅ patch-level bump
- ✅ latest version has a readable GitHub release
- ✅ no breaking/removal/deprecation marker
- ✅ extras unchanged
- ✅ no tracked issue moved
- ✅ step 1 currently green

_No residual ambiguity — nothing needed a human decision._

## Step 6 — process note

This page is the immutable record of ONE run — a later run writes its own new
page rather than rewriting this one. Annotate it freely with review notes;
nothing here is regenerated.
