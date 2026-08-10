---
type: "query"
date: "2026-08-10T04:23:07.998680+00:00"
question: "R5 asks to treat kb_setup as an SDK with proper error codes via enums. What do real tools actually do, and what should this repo build?"
contributor: "graphify"
outcome: "corrected"
---

# Q: R5 asks to treat kb_setup as an SDK with proper error codes via enums. What do real tools actually do, and what should this repo build?

## Answer

SCREENED, then RULED against my recommendation, then I was wrong about why.

Measured: modern Python SDKs do NOT use enums for error codes. anthropic-sdk-python has ZERO "from enum import" across 1,097 py files (control: 939 files match "class ", 748 match "Literal["); its typed error surface is an exception hierarchy with status_code: Literal[400] class attributes. click does the same (UsageError.exit_code = 2). openai-python is byte-identical because it is the SAME Stainless generator, so it is NOT independent corroboration.

I recommended an exception hierarchy and argued the Result reading would leave kb_setup "alone in its own ecosystem". THAT CLAIM WAS SCOPE-BROKEN: it was measured over four PYTHON projects and stated as though it covered the field. ruff has 49 "-> Result<" signatures and uv has 229 (control 0). This repo's own toolchain is Rust and Rust is Result-native. Ray ruled the Result reading; the ruling was better than my recommendation.

They were also never alternatives, which my three-way framing hid. ruff does BOTH: pub fn run(..) -> Result<ExitStatus>, returning Ok(ExitStatus::Failure) for a clean run that found lint errors. The distinction that buys is the one kb_setup most needed -- Err is "the tool broke", findings are Ok. Before this, return 1 meant both "your code is dirty" and "I failed", and return 2 meant both "you asked wrong" and "nothing ran".

The enum R5 asked for already existed, undeclared, at 175 sites (return 0 x70, 1 x34, 2 x71) with ruff's exact meanings and no declaration anywhere in code.

Rc.EXTERNAL is NOT representable as an enum member: uv's External(u8) CARRIES the code, and an IntEnum member is one fixed integer. Built as a third Result variant instead, with a range guard because subprocess returncode is NEGATIVE on a signal (-9) and would exit 247 after truncation.

Landed as PR #267. Cold review found 1 LOW: my docstring said "eight exit-code assertions" when there are seven, because I counted grep hit-lines of a loose pattern and three of them were a RUST fixture string, "fn main() {}". An unarmed counting grep in a change whose own report has a table about arming counting greps.

## Outcome

- Signal: corrected