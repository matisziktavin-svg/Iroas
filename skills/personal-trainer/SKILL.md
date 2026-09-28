---
name: personal-trainer
description: Iroas's training knowledge base and program-design procedure. Use when designing or adjusting a workout program, reviewing progress, planning progression or deloads, or giving evidence-based strength/hypertrophy advice.
---

# Personal-trainer skill

## Files

- **Knowledge base:** `references/training-knowledge.md` (next to this file)
- **Profile** (goal, history, health, schedule, equipment): `data/profile.md`
- **Program:** `data/routine.md`
- **Day-by-day log:** `data/log.md`
- **Scale readings:** `data/measurements.md`

Real sets/reps/weights live in **Hevy** — `hevy.py recent --detail` is the
source of truth. `log.md` is the consistency view only.

## When to use this

Load it for training substance: designing or revising a split, choosing
exercises or progression, planning a deload, judging whether someone is
progressing, answering "what/why should I train". For plain logging ("today was
legs") you don't need it — just update `log.md`.

## The knowledge base

`references/training-knowledge.md` covers progressive overload, frequency,
volume landmarks (MEV/MRV), intensity zones, splits, exercise selection,
periodization, deloads, biomechanics and injury caveats. **Read it before
designing or seriously adjusting a program.** Apply the relevant parts; cite the
principle when it helps them understand the "why". Don't recite it wholesale.

## Program-design procedure

Design *with* the athlete — propose, discuss, adjust. Never dump a finished
program and walk away.

1. **Gather.** `profile.md` (goal, constraints, injuries, equipment, days per
   week, session length), Hevy history if they agreed to share it, and
   `log.md` for real consistency.
2. **Choose against the knowledge base.** Split + frequency + weekly volume that
   fit the goal *and the schedule they'll actually keep*. For most people:
   2–4 days → full body or upper/lower; 4–6 days → upper/lower or
   push/pull/legs. Beginners progress on less volume than they think.
   Respect injuries. Don't add volume and intensity at the same time.
3. **Set the progression rule.** Default to **double progression**: each lift
   gets a rep window (compounds ~6–10, isolation ~10–15). When every working set
   reaches the top of the window with good form, add the smallest practical
   weight and reset to the bottom. Name a **deload trigger** (e.g. a lift stalls
   3 sessions running, or every 6–8 weeks: one week at ~half the sets).
4. **Talk it through.** Present it simply, explain the reasoning in a few
   lines, adjust to pushback. Get a clear yes before committing.
5. **Write `routine.md`.** Date it. Per day: exercises, sets × rep window, the
   current target weight, rest times. Plus the progression rule and deload
   trigger.
6. **Put it in Hevy** (see "Hevy" in your instructions): one routine per training
   day, `create` with `--dry-run` first, then for real. Record the routine IDs
   and exercise template IDs in `hevy_reference.md`.

## Progression & adjustment

- After each reviewed session: if a lift progressed, move the target (next rep
  or next weight) and push it to Hevy the same turn. If it stalled 2–3
  sessions, diagnose (sleep? volume? technique? too big a jump?) and adjust or
  deload.
- Hold a program 8–12 weeks before an overhaul. Change one variable at a time.
- Small, boring, consistent progress wins. Celebrate it.

## Body composition

If their goal involves fat loss or recomposition, scale weight alone is a weak
signal. Track weight, body fat % and muscle % (if their scale shows them) in
`measurements.md`, newest first. Falling body fat with steady/rising muscle is
progress even if the scale barely moves. Fat up / muscle down over several weeks
→ revisit training volume, progression and recovery.

## Guardrails

- Not a doctor: sharp, joint, one-sided or worsening pain → stop that movement;
  if it persists, see a professional.
- Calories/nutrition tracking is out of scope; basic protein/sleep/recovery
  guidance is fine.
