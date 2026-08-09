# R11 finding #1, resolved: `--extra-fields forbid` and `msgspec.Struct`

**Date:** 2026-08-09 · **Requirement:** R6 (models generated from
`datamodel-code-generator`), with a direct bearing on R7.

This is the independent second route Ray asked for in **R11** — *"research
independently and try to refute it, not a second opinion"* — over the parallel
`dotfiles` session's most consequential R6 finding.

## The claim under test

From `~/dev/github/ray-manaloto/dotfiles/.agent/requirements-devcontainer-gcc162.md`:

> **`datamodel-codegen` silently DROPS `unevaluatedProperties: false` for
> `msgspec.Struct` output.** pydantic emits `extra='forbid'`; msgspec emits
> nothing, and **`--extra-fields forbid` is ignored** for msgspec. Attribution
> arm: the flag *works* for pydantic. Likely upstream (`model/msgspec.py:127`
> has the mapping but never reaches it).

## Verdict

| part of the claim | verdict |
|---|---|
| the option is silently dropped for msgspec | **CONFIRMED** |
| the flag works for pydantic (their attribution arm) | **CONFIRMED** |
| *"`msgspec.py:127` has the mapping but never reaches it"* | **REFUTED** |

And the refutation is worth more than the confirmation, because it yields
something their route could not: **`--use-generic-base-class` is a working
workaround.**

## End-to-end evidence

Run against the **pinned source**, not PyPI — `uvx --from
./sources/datamodel-code-generator`, which reports
`datamodel-codegen 0.72.3.dev2+g56dff6a10`, i.e. the exact commit
`sources/datamodel-code-generator.manifest` pins. Input is one trivial
JSON-Schema object with one required and one optional property.

**Case A — msgspec, `--extra-fields forbid`, default flags:**

```python
class Widget(Struct):
    name: str
    size: int | UnsetType = UNSET
```

No `forbid_unknown_fields`. The option is accepted and discarded.

**Case B — the same, plus `--use-generic-base-class`:**

```python
class Struct(_Struct, forbid_unknown_fields=True):
    pass


class Widget(Struct):
    name: str
    size: int | UnsetType = UNSET
```

**It works.** The setting lands on a shared base class rather than per-model,
which is exactly what `CONFIG_MAPPING` describes.

**Case C — CONTROL, pydantic v2, identical flags, no generic base class:**

```python
class Widget(BaseModel):
    model_config = ConfigDict(
        extra='forbid',
    )
```

A and C differ in **one** argument (`--output-model-type`), so the probe
discriminates: it can produce both the working and the broken output, and the
difference is attributable.

## The mechanism — why "never reaches it" is the wrong description

`--extra-fields` splits at a single branch, `parser/base.py:2091-2095`:

| `use_generic_base_class` | `extra_fields` is written to | msgspec reader | pydantic v2 reader |
|---|---|---|---|
| **true** | `self.generic_base_class_config` | `CONFIG_MAPPING` via `msgspec.py:220` | its own `create_base_class_model` override |
| **false (DEFAULT)** | `self.extra_template_data[ALL_MODEL]` | **none** | `pydantic_v2/_config.py:42` |

The mapping at `msgspec.py:127` is reached through
`Struct.create_base_class_model`, called polymorphically at
`parser/base.py:4033` — live code, not orphaned. What gates it is the first line
of `__apply_generic_base_class`:

```python
if not self.use_generic_base_class or not self.generic_base_class_config:
    return
```

So the accurate statement is **"reachable only under `--use-generic-base-class`,
which is not the default"**, not *"never reaches it"*. The distinction is
practical, not pedantic: *never reaches it* describes dead code and points a
fixer at the mapping, which is correct as written. The actual gap is the
**missing default-path reader** — `grep '"extra_fields"'` across `model/`
returns exactly five hits, three in msgspec's `CONFIG_MAPPING` and two in
`pydantic_v2/_config.py`, and nothing else.

## Caveats on the workaround, stated before anyone adopts it

`--use-generic-base-class` is **not** a drop-in equivalent of pydantic's
per-model `ConfigDict`:

- It injects an extra `class Struct(_Struct, …)` into the generated module and
  renames the import to `_Struct`. That is a change to the generated models'
  **public surface**, in the same family as the `--preset` caveat their finding
  #3 raises.
- The setting becomes **module-global** rather than per-model. Any schema
  needing mixed strictness cannot express it this way.
- Only models with `SUPPORTS_GENERIC_BASE_CLASS` participate
  (`parser/base.py:~4002`), and the root-model type is excluded — so a schema
  whose target is a root model may still get nothing.

None of those were measured here beyond reading; they are flagged as the next
things to check if this workaround is adopted rather than reported.

## Probe notes

Two probes in this investigation returned answers I nearly believed:

1. **"msgspec's Jinja template ignores `extra_fields`"** — 0 hits in
   `template/msgspec.jinja2`. The control (pydantic v2's `BaseModel.jinja2`, same
   probe) is **also 0**, because pydantic handles it in Python. The probe could
   not discriminate; the real answer only appeared by grepping for the
   *consumer*.
2. **A `$GEN`-style shell variable holding a multi-word command** — zsh does not
   word-split unquoted parameters, so it resolved to a single
   `command not found` and produced a *uniform* failure across every case. A
   negative identical in all arms is one broken probe, not N results.

---

# R11 finding #2, resolved: `msgspec` and `pathlib.Path`

**The claim:** *"msgspec has NO `pathlib.Path` support in either direction —
needs a `dec_hook` AND an `enc_hook`, and they are **not global**, so they thread
through every call site. `kb_setup` is `Path`-saturated, so this is a direct cost
against R7."*

## Verdict

| part | verdict |
|---|---|
| no `Path` support in either direction | **CONFIRMED** |
| needs both a `dec_hook` and an `enc_hook` | **CONFIRMED** |
| *"not global, so they thread through every call site"* | **REFUTED as stated** — see below |
| `kb_setup` is `Path`-saturated | **CONFIRMED, and now measured** |

## Evidence — both directions, control-armed

`msgspec 0.21.1`:

```
encode: FAILS -> TypeError: Encoding objects of type PosixPath is unsupported
decode: FAILS -> ValidationError: Expected `Path`, got `str` - at `$.p`
control (datetime): b'{"d":"2026-08-09T00:00:00"}'
```

The `datetime` control matters: msgspec's built-in type coverage is real, so the
`Path` failure is a specific absence rather than "msgspec only does primitives".

## Why "threads through every call site" is not the right cost

The hooks are **per-`Encoder`/`Decoder` instance**, and one module-level pair
carries them indefinitely:

```
shared Encoder : b'{"p":"/tmp/x"}'
shared Decoder : M(p=PosixPath('/tmp/x'))
reused again   : M(p=PosixPath('/a/b'))
```

So the cost is a **convention with one seam** — construct the encoder/decoder
once, use them everywhere — not per-call-site churn. In a repo whose entire
style is "logic in a module, a seam in config", that is the shape it already has
everywhere else.

**But the trap their wording was pointing at is real, and the control names it:**

```
bare msgspec.json.encode: FAILS -> Encoding objects of type PosixPath is unsupported
```

The module-level convenience functions `msgspec.json.encode` / `.decode` do
**not** pick up the hooks. They are the obvious thing to reach for, and they fail
at runtime on any model with a `Path` field. So the requirement is a *discipline*
— never call the convenience functions — which is exactly the class of rule this
repo machine-enforces rather than documents (`TID251` banned-api would cover it,
the same mechanism §2.6j records for R4).

**One genuine per-type cost remains:** a typed `Decoder` is constructed
`Decoder(M, dec_hook=…)`, i.e. **one decoder per target model type**. An encoder
is universal; decoders are not. With N generated models that is N decoders, which
is a factory, not a hand-written list — but it is not zero.

## The `Path` tax in THIS repo, measured

The dotfiles session asked for this figure specifically. Measured 2026-08-09
over `python/src/kb_setup/`:

| | count |
|---|---|
| modules importing `pathlib` | **54 of 62** (87%) |
| `Path`-typed annotations (params, returns, containers) | **523** |
| control — `complex` annotations, same probe shape | **0** |
| control — `str` annotations, same probe shape | **813** |

Both controls are stated because a bare "523" is unreadable: the zero proves the
probe can return nothing, and the 813 gives the scale — **`Path` is 64% as
common as `str` in this codebase.** That is the R7 cost, and it is large enough
that "one shared encoder plus a decoder factory" is a materially different
proposition from "thread hooks through 523 sites". The refutation above is
therefore load-bearing, not a quibble.

## Version caveat

Tested against `msgspec 0.21.1` — the **installable** version from PyPI, which
is the currency doctrine's "installable truth". `sources/msgspec.manifest` pins
commit `593ec549`, which may be ahead of that release; if a future round finds
`Path` support has landed upstream, this finding expires and the manifest is
where to check.

## GitHub repos touched

- [koxudaxi/datamodel-code-generator](https://github.com/koxudaxi/datamodel-code-generator)
  — the source under test; read at the pinned commit `56dff6a1` and executed
  from that clone.
- [jcrist/msgspec](https://github.com/jcrist/msgspec) — `forbid_unknown_fields`
  is a `StructConfig` option implemented in `src/msgspec/_core.c`; confirmed
  present via `graphify explain`.
