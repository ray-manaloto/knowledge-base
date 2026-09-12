---
type: "query"
date: "2026-09-12T20:52:27.801616+00:00"
question: "Why did kb-mod-runtime-check return rc 127 when the claude binary was installed and working?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why did kb-mod-runtime-check return rc 127 when the claude binary was installed and working?

## Answer

`mise run kb-mod-runtime-check` failed **rc 127** on 2026-09-12 and a review lane
attributed it to contention from a concurrent 5-lane run. That was wrong, and the
correct diagnosis came from CHANGING THE INSTRUMENT, not from looking harder.

The chain, each hop a different route:

| probe | result |
|---|---|
| `claude --version \| head` | printed an error and **rc=0** — the pipe returning `head`'s code |
| the same, redirected to a file | **rc 1**, `Error: claude native binary not installed` |
| `command -v claude` | a mise shim, which `readlink -f` resolves to **`mise` itself** |
| `mise which claude` | `~/.local/share/mise/installs/node/26.8.2/bin/claude` |
| the 207,500,480-byte native binary, run **DIRECTLY** | **rc 0**, `2.1.270 (Claude Code)` |
| `cat bin/claude.exe` (500 bytes) | a **placeholder shell script** that unconditionally echoes the error and `exit 1`s |

**The vendor's own error message was false.** It says *"either postinstall did not
run ... or the platform-native optional dependency was not downloaded"* — the
dependency WAS downloaded, present and working. Only `install.cjs`, the postinstall
that swaps the placeholder launcher for the real binary, never ran. mise's npm
backend installed the package with scripts disabled and left the stub.

**Fix: `(cd <pkg> && node install.cjs)`, rc 0.** `bin/claude.exe` becomes a
hardlink to the 207 MB binary; the shim returns rc 0; the gate returns rc 0 clean.

Three durable points:

1. **Two probes disagreeing located the bug for free.** The binary and its launcher
   gave opposite answers about the same tool. No amount of re-reading the error
   message would have got there — only a different instrument. The one that was
   wrong was the one printing the message.
2. **A "not installed" message is written by something that cannot know.** It is a
   stub. Treat a vendor's diagnosis of its own absence as a hypothesis.
3. **rc 127 in a transcript reads exactly like the thing under test failing.** The
   gate classifying it as NOT_RUN rather than a pass is what kept this honest —
   and it is the same class as an unbounded probe against an absent binary.

Related, same family: this is an npm-backend tool under mise whose lifecycle
script did not complete — the same shape as the 2026-08-24 `node-gyp` shim
recursion that wedged every `mise run`. Whether mise runs npm lifecycle scripts at
all is the durable question, and it belongs to the dotfiles project.


## Outcome

- Signal: useful