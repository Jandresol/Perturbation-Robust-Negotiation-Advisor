# Perturbation-Robust Negotiation Advisor

An AI-assisted tool that helps a human team prepare for and participate in a two-team, mixed-motive negotiation. LLMs interpret the scenario and develop options during preparation. During negotiation, a non-LLM planner updates recommendations from confirmed exchanges. Humans make every decision.

## 1. The idea in one minute

Both teams get the same shared package plus their own private role card. We play one side and want the best outcome for our side. We do not assume the other side has to lose for us to win.

The system works in three layers:

1. **LLMs turn text into a game.** The inference engine converts the package into a *commitment game* in the style of Benac et al. (2026): actions each side can commit to, goals those actions satisfy, and a goal-utility matrix `G`. Our column of `G` is inferred from our role card. The opponent’s column is estimated from the evidence available to us, because we only partly know what they value.
2. **A non-LLM planner solves the game.** It computes which commitments to trade, in what order, and when to walk away. Accepted commitments are binding and additive.
3. **LLM advisors check and explain the plan.** A strategic advisor reviews what the game leaves out; an ethics advisor flags or vetoes moves against established constraints. The result is a one-page brief with a short menu of options. Humans choose what to do.

**The perturbation we study is rewording only.** Individual extracted facts are expressed differently while preserving meaning, attribution, uncertainty, conditions, numbers, and red lines. The underlying game and the set of optimal plans should remain unchanged. Wording-induced changes are tested as invariance failures, separately from same-text stochastic variation and equally good alternative plans. No gold labels are needed to detect inconsistency; determining which advice is correct or worse requires additional evaluation.

**The readings also generate strategies.** Each rewording may yield a different inferred game. Across the `K` readings, we:

- Pool each reading’s best plan and retain candidates that score well across all readings, checking both average and worst-case scores.
- Build a **contingent strategy** where competing opponent models justify one: a probing opening, followed by branches based on observed acceptance or rejection.
- Maintain strategically distinct, high-quality alternatives through a quality-diversity archive.

The readings are alternative estimates of the same negotiation, not new information. Their frequencies are not automatically calibrated probabilities of actual opponent types.

**Why rewording first?** It fits the approximately eight-week scope and isolates representation sensitivity. Fact-changing counterfactuals belong to Plan B.

## 2. Research questions and hypotheses

When a package’s facts are reworded without changing meaning:

- **(a) Sensitivity:** How much do strategies change, where does the change enter the pipeline, and how does it relate to embedding-space distance?
- **(b) Aggregation:** Does aggregating reworded readings produce better, more stable strategies than a single reading and repeated identical-text readings at equal compute?
- **(c) Creativity:** Does pooling produce a larger menu of robust, near-optimal plans, including contingent strategies, than identical-text resampling or direct sampling of opponent utilities?

The primary comparison is **whether rewording-based aggregation reduces decision-quality loss relative to repeated readings of identical text at equal compute**.

| ID | Hypothesis | Rationale |
|---|---|---|
| H1: Brittleness exists | A single-reading pipeline changes plans under valid rewordings at a non-trivial rate. | Meaning-preserving changes can affect LLM behavior. |
| H2: Wording versus noise | At matched embedding distance, compare sensitivity to valid rewordings and random surface noise. The proposed hypothesis is comparable sensitivity. | Tests surface-form sensitivity; unvalidated noise is a secondary stress test, not a semantic control. |
| H3: Where it enters | Most material plan changes arise from opponent-utility inference near acceptance thresholds. | Small errors can flip predicted acceptance. Own-utility error bounds alone do not establish this empirical hypothesis. |
| H4: Aggregation helps | Rewording × K lowers regret and instability versus a single reading and same-text resampling × K. | Aggregation can reduce variance; the utility benefit must be measured. |
| H5: The planner helps | The planner pipeline is less brittle than an LLM-only advisor. | A deterministic planner isolates wording effects to its inferred inputs; downstream advisor changes are measured separately. |
| H6: A better menu | Rewording produces more distinct near-optimal plans than same-text resampling (B2) or direct opponent-utility sampling (B9), without reducing true utility. Contingent plans can outperform a fixed plan when responses are informative. | Different readings can expose overlooked structures and trades; cross-scoring screens candidates before independent evaluation. |

No improvement over resampling is a valid result. Creativity means useful differences in commitment packages, sequencing, or response branches, not differences in prose.

## 3. Preparation: 12 minutes

| Time | Activity |
|---|---|
| 0:00–1:30 | Build a single-reading game and fallback plan. |
| 1:30–5:00 | Process fact rewordings, generate plans, cross-score candidates, and review strategic and ethical concerns. |
| 5:00–6:00 | Stop generation and assemble the brief from validated results. |
| 6:00–12:00 | The team reviews sources, checks assumptions, and chooses an opening and fallback. |

These are target timings for rehearsal. The one-page brief contains a trade-off table, opening offer, alternatives, walk-away point, red lines, critical assumptions, and a short contingent decision tree.

## 4. Live negotiation: 12–15 minutes

One teammate operates the interface while the others negotiate.

1. Record an offer, response, or agreement using structured controls.
2. Confirm the event before updating the game state.
3. Update commitments and beliefs about the opponent’s preferences.
4. Re-plan and display a next-move card with an offer, fallback, value estimates, and relevant flags.

Perturbations run during prep only. No LLM is required for live action selection. Voice or text parsing is optional; the initial interface uses structured entry. A printed decision tree provides a fallback. Live classroom use follows course rules.

Disagreement across readings measures variation in the system’s interpretation. It is not automatically a calibrated probability distribution over human opponent types.

## 5. Creative strategy search

Quality-diversity search maintains a menu of useful alternatives rather than selecting only one winner.

- **MAP-Elites-style archive:** retain strong plans across categories such as issue linkage and acceptance conservatism.
- **Rainbow-inspired mutation:** generate grounded variations of fact wording or candidate plans, then validate and score them.
- **Vendi score:** measure diversity using structured plan features rather than differences in prose.

Candidates can explore logrolling, bundled commitments, sequencing, and contingent responses. Every candidate must remain feasible, source-supported, and consistent with red lines. Novelty alone is insufficient. CMA-ES is not a dependency.

## 6. Evaluation

The main comparison uses the same inference engine, planner, archive, and selection rules:

| Condition | Input |
|---|---|
| Single reading | Original extracted facts |
| Same-text aggregation | Repeated processing of identical facts |
| Rewording aggregation | Processing of meaning-preserving fact variants |
| Direct utility sampling (B9) | Sampling opponent utilities from a single-reading estimate, with the same pooling and contingent planning |

Account for rewording generation and validation in the compute budget. Report tokens, calls, solver evaluations, and wall time. Evaluate on held-out base scenarios and independently generated rewordings.

On generated games with known utilities, measure regret against an information-matched reference policy, agreement rate, and constraint violations. Assess creativity through quality-filtered diversity, archive coverage, and distinct useful plans. Human audits check that accepted rewordings preserve meaning.

The classroom exercise evaluates preparation time, operator workload, recommendation usefulness, overrides, and the observed agreement. It is a case study; inferred utility scores alone do not establish real-world success.

## 7. Initial build

1. Source-linked fact extraction and utility inference.
2. Deterministic small-game planner and fallback brief.
3. Fact rewording, semantic checks, and same-text sampling control.
4. Cross-scoring, quality-diversity archive, and strategy menu.
5. Structured live interface with confirmed event logging and re-planning.

## 8. References

- [Benac et al. (2026): Commitment-game benchmark](https://arxiv.org/abs/2603.14066)
- [Ma et al.: Humanitarian negotiation interface design](https://arxiv.org/abs/2410.09139)
- [Mouret and Clune (2015): MAP-Elites](https://arxiv.org/abs/1504.04909)
- [Samvelyan et al. (2024): Rainbow Teaming](https://arxiv.org/abs/2402.16822)
- [Friedman and Dieng (2023): Vendi score](https://arxiv.org/abs/2210.02410)
