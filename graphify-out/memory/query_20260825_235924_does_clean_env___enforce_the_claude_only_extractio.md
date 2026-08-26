---
type: "query"
date: "2026-08-25T23:59:24.336888+00:00"
question: "Does clean_env() enforce the Claude-only extraction invariant?"
contributor: "graphify"
outcome: "corrected"
correction: "A fact learned from a report, restated without re-reading the code, propagates\nthe report's error under the authority of the person restating it.\n\nI told Ray that clean_env() is what enforces the Claude-only extraction\ninvariant. It is not, and his own directive of the same day warns in as many\nwords that this specific misattribution exists and that a naive rewrite\npreserves it. Verified in the code afterwards: llm.py:3412's detect_backend()\nfallback loop excludes both claude-cli and openai-cli, so neither was ever\nauto-selectable and clean_env() never enforced the CLI carve-out. clean_env()\ndoes strip OPENAI_API_KEY, and that strip must stay -- it is what keeps\nopenai-cli on the ChatGPT subscription instead of falling through to metered\nAPI spend -- but that is a different mechanism from the one I credited.\n\nThe deeper failure was reading the tail of a directive file and not its body. I\nread the codegen addendum at the bottom of the 2026-08-25 directives and never\nread section 2, which is where Ray had already ruled that claude-cli and\nopenai-cli are both sanctioned graphify agents and that do-not.md #4's phrasing\nshould be removed or refactored. I then spent a grilling round asking him to\ndecide something he had already decided. A directive file is read to the bottom\nAND from the top; the newest addendum is not the whole document.\n\nA second, cheaper failure in the same round: a control arm reported a failing\ncommand combination as passing, because the twenty flags were written into a\nshell variable and this shell does not word-split an unquoted variable, so all\ntwenty arrived as one argument and none applied. The arm tested nothing and\nlooked clean. Written properly, the answer reversed. A probe whose flags are\nassembled in a variable must be shown to have delivered them.\n"
---

# Q: Does clean_env() enforce the Claude-only extraction invariant?

## Answer

The round asked whether switching graphify's extraction backend from claude-cli
to openai-cli required changes to the skills, the kb-build mise task, and the
python modules it calls. The answer is no on all three, and the real blocker was
somewhere else entirely.

kb-build has no LLM backend to switch. Its own task description reads
"deterministic, no LLM": it clones each pinned source, AST-extracts code for
free, and replays the already-committed sources/extractions chunks. grep for
`backend` in its module returns nothing.

There are three separate LLM paths and only one carries a --backend knob. The
host-agent fan-out (kb-add -> subagents -> chunks -> kb-merge) is what actually
produces corpus chunks, and Claude Code itself is the model there, so there is
no provider call to redirect; kb-extract.js has zero backend mentions.
graphify_native_extract already accepts --backend openai-cli with both guards,
shipped in 118032e4 (PR #514, merged, 8/8 arms died). kb-label --claude-cli is
opt-in and already broken upstream with a deterministic fallback.

The actual blocker is at the graphify->codex boundary and is a fork defect.
Before calling codex, graphify disables the caller's MCP servers so extraction
does not boot them. It asks codex for the list (10 on this machine), then sends
one disable-override per name. Only 5 have a real [mcp_servers.NAME] entry in a
config file; the other 5 are registered by codex plugins. An override naming a
server with no entry creates a table carrying neither command nor url, and codex
rejects the entire configuration with "invalid transport". Every prose
extraction therefore dies in about three seconds, before spending anything.

Two-arm split, same flags, same env, same cwd, differing only in the names sent:
the 5 config-defined names returned rc 0; the 5 plugin-only names returned rc 1
with the invalid-transport error. Reproduced outside graphify entirely, driving
codex directly.

A control arm established that the fork itself is healthy: a code-only
extraction through the forked CLI with --backend openai-cli returned rc 0 and
wrote 45 nodes, 67 edges and 12 communities. Code needs no provider, so that run
exercised the fork without touching the broken path.


## Outcome

- Signal: corrected
- Correction: A fact learned from a report, restated without re-reading the code, propagates
the report's error under the authority of the person restating it.

I told Ray that clean_env() is what enforces the Claude-only extraction
invariant. It is not, and his own directive of the same day warns in as many
words that this specific misattribution exists and that a naive rewrite
preserves it. Verified in the code afterwards: llm.py:3412's detect_backend()
fallback loop excludes both claude-cli and openai-cli, so neither was ever
auto-selectable and clean_env() never enforced the CLI carve-out. clean_env()
does strip OPENAI_API_KEY, and that strip must stay -- it is what keeps
openai-cli on the ChatGPT subscription instead of falling through to metered
API spend -- but that is a different mechanism from the one I credited.

The deeper failure was reading the tail of a directive file and not its body. I
read the codegen addendum at the bottom of the 2026-08-25 directives and never
read section 2, which is where Ray had already ruled that claude-cli and
openai-cli are both sanctioned graphify agents and that do-not.md #4's phrasing
should be removed or refactored. I then spent a grilling round asking him to
decide something he had already decided. A directive file is read to the bottom
AND from the top; the newest addendum is not the whole document.

A second, cheaper failure in the same round: a control arm reported a failing
command combination as passing, because the twenty flags were written into a
shell variable and this shell does not word-split an unquoted variable, so all
twenty arrived as one argument and none applied. The arm tested nothing and
looked clean. Written properly, the answer reversed. A probe whose flags are
assembled in a variable must be shown to have delivered them.
