The system runs in two phases with very different time budgets. Prep is LLM-heavy. During the negotiation, no LLM is in the decision loop: only the planner runs, which takes milliseconds on a game this size.

Phase 1: prep (12 minutes)

┌────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│   Clock    │                                                           What happens                                                           │
├────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 0:00–1:30  │ Package → facts → game built from a single reading → first plan and trade-off table. This is the fallback if anything later      │
│            │ fails.                                                                                                                           │
├────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 1:30–5:00  │ K rewordings in parallel → K games → candidate pool → re-score on every reading → menu plus contingent tree (§6.6). Advisor and  │
│            │ ethics review.                                                                                                                   │
├────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 5:00–6:00  │ Hard cutoff. The aggregator writes the brief from whatever has finished.                                                         │
├────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ 6:00–12:00 │ The team reads the one-page brief and picks a plan from the menu.                                                                │
└────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

What the team takes into the room:
- the walk-away point;
- the trade-off table (what to give, what to ask for, red lines);
- the recommended opening;
- the contingent tree, e.g. "if they reject a3 ↔ b2, they're probably type θ₂ → switch to branch B";
- the 3 facts the plan depends on most;
- the ethics flags.

The contingent tree you added in §6.6 is what makes the system usable live even without a laptop. It's a decision tree you can print.

Phase 2: the negotiation (12–15 minutes)

One teammate acts as the operator. The others negotiate. The operator runs this loop after every exchange:

1. Log the event (~5 s). The screen shows the game's actions as buttons with short labels ("b2 guard rations", "a3 end diversion"). The operator taps what was offered or agreed, or types shorthand ("they want a1+a4, offer b1"). An LLM parser turns free text into a structured offer. The operator confirms with one tap, so a parse error never enters the game state unconfirmed.
2. Update the state. If an offer was accepted, C is updated; that commitment is binding.
3. Update the opponent-type weights. Each type θ_j from the readings predicted accept or reject. With a noise rate β (real opponents sometimes reject offers for tactical reasons, say β ≈ 0.3):
   w_j ← w_j · (1−β if θ_j predicted the observed response, else β), then renormalise.
   This moves you along the contingent tree and is calibrated rather than hard-coded.
4. Re-plan (< 1 s). Exact search from the current C. The remaining turns are estimated from the clock: minutes left ÷ the average time per exchange measured so far. Valuable concessions are held for the end (deadline effect).
5. Show the next-move card.
   - The next offer and a fallback.
   - Accept or reject their latest offer, showing our value against the walk-away point and its margin (Prop. A4).
   - The current belief about their type.
   - Any ethics flag.

Total latency is about 5–10 seconds, almost all of it the operator's input.
