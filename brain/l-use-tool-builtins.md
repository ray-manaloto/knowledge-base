---
kind: lesson
source: feedback_use_tool_builtins
---

# l-use-tool-builtins

Check a tool's official facts and canonical patterns before adding detection variables, environment parsing, or helper scripts.
Custom container detection once duplicated chezmoi's built-in OS fact and enabled a stale-config path that could affect host files.
Prefer declarative built-ins across chezmoi, mise, hk, uv, Docker, and GitHub Actions.
When custom logic is truly necessary, document why the built-in cannot distinguish the required states under [[routing-doctrine]].
