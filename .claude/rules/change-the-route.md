# Change the Route, Not the Care: A Wrong Answer Survives Re-Reading

When a claim about **where something is declared, defined or configured**
surprises you — or simply matters — the fix is a probe down a **different
route**, never a more careful read of the same one. Nine wrong claims in a
single round (2026-09-11) were each made carefully by someone who believed they
had probed it. **Not one was caught by re-reading.** Every one fell to a
different instrument.

This is the sibling of `probes-need-a-control-arm.md`, and the distinction is
the point. That rule asks *can this probe produce the other answer?* This one
asks *is this the right instrument to be asking with?* A probe can be perfectly
control-armed and still be the wrong tool — a `grep` that discriminates real
matches from fake ones, run against a file format it cannot parse.

## The nine, all one shape

A plausible file or rule named without the probe that would settle it:

| # | the claim | what refuted it |
|---|---|---|
| 1 | "`mise.toml` pins claude-code 2.1.251" | reading `mise.toml` |
| 2 | "the pin is in the user-global config" | reading that config |
| 3 | "declared by no config at all" | `grep -rl` including backups |
| 4 | citation offset **+31** | it was a fact about ONE copy |
| 5 | citation offset **+59** | arithmetic against the real blob |
| 6 | `readlink -f "$(command -v claude)"` finds claude | it resolves to **mise** |
| 7 | "the backup is the only file declaring it" | a second match existed |
| 8 | a control arm grepping `claude-code\|claude_code\|anthropic` | bare `grep claude` → **31** hits |
| 9 | "these are the authoring requirements" | **compiling** a handler |

Five were an advisor lane's, four were the session's. Seniority did not help,
and neither did knowing the pattern: instances 5, 7 and 8 were made *after* the
pattern had been named out loud.

## The routes that actually settled things

Note that none of these is "the same probe, done better":

```
config-read      ->  TOML parse          (only a [tools] parse answers "is it declared?")
grep -n          ->  sed -n              (a line number is not a line)
grep -rl         ->  file(1)             (a "match" was a Mach-O BINARY)
bare basename    ->  explicit path       (two hook_guard.py exist across two repos)
reading a type   ->  COMPILING against it (the type ADMITS what the prose forbade)
command -v       ->  an explicit path    (a shim shadowed the real binary)
```

## Rules

1. **A location claim needs a location probe.** "Where is X declared?" is
   answered by parsing the format that declares it, not by grepping for its
   name. A narrow grep reads as clean absence; a bare grep reads as presence via
   comments, tasks and aliases. **Both mislead, in opposite directions.**
2. **A behaviour claim needs the behaviour.** Reading a type declaration tells
   you what it *says*; compiling a candidate against it tells you what it
   *permits*. Those differ, and the gap is exactly where an "authoring
   requirement" turns out to be a preference.
3. **A `grep -rl` match is not a file of the kind you assumed.** It matches
   bytes. Run `file(1)` on anything surprising before describing it — one
   "config declaring the tool" was a stranded 203 MB executable.
4. **A bare basename is ambiguous across repos, and silently resolves wrong.**
   Two `hook_guard.py` files, 525 and 835 lines; a citation to `:685` is valid
   in one and out of range in the other. Cite a path, not a name.
5. **An offset, a line number and a version are facts about WHICH COPY you
   read.** They do not transfer between readers, even inside one session. Pin
   the artifact by commit and sha; quote the bytes, and treat the line number as
   navigation rather than evidence.
6. **`command -v` is not "where the tool is".** A shim can shadow the real
   binary, and the shim answers *plausibly* — one probe through it returned a
   single tidy result from an entirely different program, with no error.

## The failure mode this closes, stated plainly

**A wrong answer from the wrong instrument does not look wrong.** It looks like
an answer: one hit, a clean `rc=1`, a line that exists. Nothing about it invites
a second look, which is why more care on the same route never catches it — care
is spent on reading the output, and the output is fine. Only a different
instrument disagrees, and *disagreement is the signal*.

So when two probes of one fact disagree, do not adjudicate by re-reading either.
Ask which instrument can actually see the thing.

## Applies to

Every claim about where something lives or what a contract permits: pins,
declarations, registrations, hook wiring, line citations, tool resolution, and
any statement of the form "the only place X appears is Y".

## See also

- `probes-need-a-control-arm.md` — the sibling: *can* this probe produce the
  other answer? Necessary, and not sufficient — instance 8 above was a control
  arm that proved the file was readable and never that the term was right.
- `verify-before-advancing.md` — read the real `rc`; this rule is about reading
  it from the right command.
- `use-tool-builtins.md` — the instrument you need is usually one a tool already
  ships (`file`, a TOML parser, the compiler), not a cleverer grep.
