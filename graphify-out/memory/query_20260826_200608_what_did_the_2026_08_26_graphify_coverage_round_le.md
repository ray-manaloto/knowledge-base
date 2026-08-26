---
type: "query"
date: "2026-08-26T20:06:08.743064+00:00"
question: "What did the 2026-08-26 graphify-coverage round learn about probes, delegated lanes, and whether this corpus is actually being used?"
contributor: "graphify"
outcome: "useful"
---

# Q: What did the 2026-08-26 graphify-coverage round learn about probes, delegated lanes, and whether this corpus is actually being used?

## Answer

The round built `kb_setup.code_intel` (five provenance-tagged lanes, 449
cross-layer edges, 7/7 mutation arms), unparked `kb-graphify-native-extract`,
rescued 164 KB of prototype work plus an unpushed fork fix from `/tmp`, filed
eleven issues, and published five artifacts. But the durable lessons are about
how the work went wrong, not what it produced.

**A control arm must cover the TERM, not just the TOOL.** I reported a codex
implementer lane dead — twice, confidently — on `pgrep -f 'codex exec'`
returning nothing. I control-armed it with `pgrep -f 'Claude'`, which proved
`pgrep` WORKS and said nothing about whether `'codex exec'` is how that process
appears. It is not: the live process was a codex-*companion* shell (PID 78477)
carrying this session's own id, and it was working the entire time. It later
wrote a 28 KB module and augmented my test file while I was committing.
`probes-need-a-control-arm.md` rule 3 already names this — "A TOKEN SPELLING is
a bound too, the most common form" — and I walked into it anyway, because
arming the tool FEELS like arming the probe.

**A mutation arm found a defect in my own test, not in the code.** A7 SURVIVED:
my assertion accepted `(ValueError, KeyError)`, so deleting the module's guard
entirely still passed, because the dict lookup raises `KeyError` one line later.
The test was incapable of failing and looked thorough. This is the whole value
of `kb-arms` in one row, and it happened on a test file I wrote *specifically
because I did not trust code I had not authored*.

**The corpus was used zero times while three lanes read its source by hand.**
A 13,442-node deep extraction of graphify's own source sits on disk, free to
query. The SDK-parity question, the backend-failover question and the
step-surface question were all answered by dispatching agents to read `llm.py`
and `cache.py` directly. The reason is one bad query: asking about "the
extraction backend" without `--prose` or `--idf` returned 2,204 nodes of
vendored Rust, which I read as the graph being unhelpful. Re-run with
`--prose --idf` and the graph's own vocabulary, the same corpus returned 16
sharp, source-cited hits. Both flags are documented in the root `CLAUDE.md`.
The graph-first hook fired, a query ran, and the guard was satisfied — **a guard
that checks whether you asked cannot check whether you asked well.**

**Two published claims were wrong for the same reason: I took a rule's shape
instead of reading its text.** "6 invariant-banned verbs" is really 2 — and one
of the four wrongly counted is `watch`, a verb `do-not.md` had ALREADY corrected
itself about, in the very entry I misread. "This repo is project-Claude-only"
is false: it runs codex lanes, antigravity reviews, and an openai-cli backend.
Both reached an issue and an artifact before Ray caught them.

**Read-only agent types have no incremental fallback.** Nine of ten lanes
returned nothing; eight survived because I made them write to disk as they went.
The `premise-verifier` could not be given that instruction — it has no Write
tool by design — so its findings are simply gone, and the premises it was
verifying had to be checked by hand. Two of my own premise rows were refuted in
that check, including a guessed chunk schema that would have emitted a chunk the
validator rejects.

**graphify has no honest place for a whole class of node.** Its `_origin` takes
exactly two values, `ast` and `semantic`. A mise task node, a skill-fence node
and a config-read node are neither — deterministic, zero-token, not source AST.
Stamping `semantic` is a false provenance claim; omitting it means graphify
reads the location as AST and silently drops the node (629 lost that way once).
So `code_intel`'s chunk deliberately does not merge, and that is the correct
state rather than a missing line of code.


## Outcome

- Signal: useful