# Lane: refute-antigravity-pin — adversarial verification (2026-08-18)

FINDING UNDER TEST: "antigravity-cli: the pin governs nothing that runs and Ray's
1.1.13 instruction was never committed. mise.toml pins 1.1.11; the binaries
self-update in place inside the 1.1.11-labeled dir: agy reports 1.1.14,
antigravity reports 1.1.13. No commit ever added '1.1.13' to mise.toml. Drift
structurally invisible to kb-currency-check (no [tool.antigravity-cli] table)."

Status: IN PROGRESS — probes running. Sub-claims:
(a) mise.toml:132 pins 1.1.11 — UNVERIFIED
(b) binaries self-update IN PLACE inside the 1.1.11-labeled mise dir — UNVERIFIED
(c) agy --version -> 1.1.14; antigravity --version -> 1.1.13 — UNVERIFIED
(d) no commit ever added '1.1.13' to mise.toml (control: -S '1.1.11' must be non-empty) — UNVERIFIED
(e) Ray's 1.1.13 instruction never committed anywhere — UNVERIFIED (checking docs/direction + repo-wide -S)
(f) currency.toml has no [tool.antigravity-cli] table (control: other [tool.*] present) — UNVERIFIED

## Probe log

(appended as run)
