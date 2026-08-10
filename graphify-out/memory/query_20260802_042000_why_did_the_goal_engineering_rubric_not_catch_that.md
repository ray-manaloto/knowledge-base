---
type: "query"
date: "2026-08-02T04:20:00.374538+00:00"
question: "Why did the goal-engineering rubric not catch that a well-formed goal can run as an unbroken silence?"
contributor: "graphify"
outcome: "corrected"
correction: "Passing every rubric test does not make a goal well-formed, because all thirteen tests asked whether the EVALUATOR could settle the condition and none asked whether the OPERATOR could see progress. The Settled goal passed 15/15 mechanical checks and every judgement test, then ran as an unbroken silence Ray read as 'done and agents completed' minutes after arming — with TaskList and CronList both empty. Fix: a T14 operator-visibility test, and the obligation lives in the RIDER (phase-boundary messages, a warning before any >2min command, turn count against the bound) and NEVER in the goal, because a checkpoint the goal can be satisfied by is a round that announces itself (T10/T12). The /goal docs already imply it: with a turn clause, 'Claude reports progress against that clause each turn'."
---

# Q: Why did the goal-engineering rubric not catch that a well-formed goal can run as an unbroken silence?

## Answer

All thirteen tests asked whether the EVALUATOR could settle the condition; none asked whether the OPERATOR could see progress. The Settled goal passed 15/15 mechanical checks and every judgement test, then produced silence that Ray read as 'done and agents completed' minutes after arming, with TaskList and CronList both empty. Fix: T14 operator visibility, and the obligation lives in the RIDER (phase-boundary messages, a warning before any >2min command, turn count against the bound) never in the goal, because a checkpoint the goal can be satisfied by is a round announcing itself (T10/T12). The /goal docs already imply it: with a turn clause, 'Claude reports progress against that clause each turn'.

## Outcome

- Signal: corrected
- Correction: Passing every rubric test does not make a goal well-formed, because all thirteen tests asked whether the EVALUATOR could settle the condition and none asked whether the OPERATOR could see progress. The Settled goal passed 15/15 mechanical checks and every judgement test, then ran as an unbroken silence Ray read as 'done and agents completed' minutes after arming — with TaskList and CronList both empty. Fix: a T14 operator-visibility test, and the obligation lives in the RIDER (phase-boundary messages, a warning before any >2min command, turn count against the bound) and NEVER in the goal, because a checkpoint the goal can be satisfied by is a round that announces itself (T10/T12). The /goal docs already imply it: with a turn clause, 'Claude reports progress against that clause each turn'.