---
name: artifact-download
description: "Plan a provider-neutral immutable artifact transfer and publish a bounded atomic receipt. Use only with a reviewed provider adapter, credential-free source identifier, and full revision."
---

# Immutable artifact download

This skill is a thin boundary:

```bash
mise run kb-artifact-download -- $ARGUMENTS
```

Arguments are `provider source revision destination [plan|apply] [receipt]`.

The command plans by default. Pass the positional `apply` mode to transfer with
an exact reviewed provider adapter, a full immutable revision, and a bounded
declared byte inventory. The mise task translates that mode to its internal
flag. The current repository intentionally ships no provider adapter, so the
public command refuses rather than choosing a network or credential source.

Receipts contain only structural identifiers, byte counts, and SHA-256 values.
They never authorize archive extraction, model execution, media processing,
Colibri control, automatic adoption, or writes outside the explicit artifact
destination and receipt.
