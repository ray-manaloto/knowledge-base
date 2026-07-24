---
kind: lesson
source: feedback_research_before_fixing
---

# l-research-before-fixing

Debugging starts with complete logs, official documentation, and comparable real-world implementations, not a guessed fix.
On 2026-03-29, an assumed transient Ubuntu 25.10 snapshot failure suggested retries.
Research showed comparable projects did not use snapshot pinning, supporting removal of the unreliable mechanism instead.
Apply [[verification-discipline]] by confirming root cause and citing concrete sources before proposing a repair.
