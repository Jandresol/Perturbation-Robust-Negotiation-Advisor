# Plan A — Rewording-Only Perturbation

> Living document. One of two alternative plans; the other is
> `PLAN_B_COUNTERFACTUAL.md`, and `PLAN_COMPARISON.md` weighs them.
> `PROJECT_PLAN.md` is the earlier combined plan and is left unchanged.
> Sections marked **[DECIDE]** are open; **[ASSUMPTION]** are defaults.

Last updated: 2026-10-20 · Owner: Vedant Sandhu · Course: COMPSCI 2822R

---

## 0. TL;DR

We build a multi-agent advisor for a **turn-based, two-team, non-zero-sum
negotiation**. LLMs turn the negotiation package into a commitment game
(Benac et al. 2026): actions, goals, and a goal-utility matrix `G` with our
column known and the opponent's column estimated. A non-LLM planner computes
which commitments to trade and in what order. LLM advisors check and explain
the plan.

The only perturbation is **rewording**: the same facts said in different
words. Meaning does not change, so the true game and the optimal plan do not
change. Any change in the advice is error caused by wording.

**Research question.**
> When a package's facts are reworded without changing their meaning,
> (a) how much do the suggested strategies change, at which pipeline stage
> does the change enter, and does it track the embedding-space distance
> between original and reworded facts? (b) Does aggregating over rewordings
> produce better and more stable strategies than one reading, at equal
> compute — and better than simply resampling the same text?

---

## 1. Scope and assumptions

### 1.1 Non-zero-sum  **[ASSUMPTION]**
The two teams' payoffs do not sum to a constant: some outcomes are better or
worse for both. Our objective is our own utility; joint value is tracked as a
secondary metric. **[DECIDE]** whether to also assume a positive zone of
agreement: some `C` with `r_us(C) > r_us(C⁰)` and `r_opp(C) > r_opp(C⁰)`.

### 1.2 What counts as a rewording  **[ASSUMPTION]**
A rewording changes the words, not the meaning. Allowed operators:

| Operator | Unit | What changes |
|---|---|---|
| `paraphrase_fact` | one atomic fact | wording of that fact |
| `paraphrase_doc` | one source document | wording of the whole document |
| `reorder` | package | order of documents / facts |
| `register` | document | tone or register (formal ↔ plain), same content |

**Excluded** (they change content, not wording): inserting distractor facts,
dropping facts, gain/loss reframing that changes emphasis enough to fail the
entailment test, and every counterfactual shift (Plan B).

Each rewording is **accepted** only if: cosine similarity to the original
≥ `τ` **and** bidirectional NLI entailment **and** hard facts (numbers,
names, red lines) are unchanged. A 5% sample is checked by a human.

### 1.3 Game model, adopted from Benac et al. (2026)
| # | Benac assumption | Our use |
|---|---|---|
| A1 | Binding commitments; can be added, never withdrawn | Adopted |
| A2 | Goals need specific commitments; `G` gives each player's value per goal; goals are linear or all-or-nothing | Adopted; `G` built from text (§4) |
| A3 | Bilateral turns: propose, accept/reject | Adopted; proposer alternates. Non-players (mayor, militia, NGOs) enter as goals or constraints |
| A4 | Everyone knows everyone's utilities | **Relaxed**: `G_us` from our role card; `G_opp` estimated as `π(G_opp)` |
| A5 | Agents are planners / RL | **Hybrid**: planner optimises; LLMs build the game, review, and explain |

### 1.4 Train / validate / test
| Split | Data | Time limit |
|---|---|---|
| Train | Generated Benac games rendered as text; Sim 1 | none |
| Validate | Held-out generated games; Sim 2 | none |
| Test | Live exercise package, unseen | 12 min prep (brief in ≤ 6 min), 12–15 min negotiation |

Frozen artifacts carried to the test: rewording operators and thresholds,
the game builder prompts, the aggregation rule and `K`, advisor and ethics
prompts.

### 1.5 Open decisions
- **[DECIDE]** Is a deal preferred over no deal? Parameter `deal_bonus`;
  report results for `{0, small, large}`.
- **[DECIDE]** Is the package available before prep starts? Assume no.
- **[DECIDE]** Is live AI use allowed during the negotiation?
- **[DECIDE]** Which side we play in each pack.
- **[DECIDE]** Benac code access (anonymous review link).

---

## 2. Background (what this plan relies on)

- **Negotiation analysis:** Raiffa (1982), Lax & Sebenius (1986), Fisher &
  Ury (1981): multi-issue scoring, BATNA, logrolling, ZOPA.
- **Benac, Raedler, Ma & Doshi-Velez (2026, arXiv 2603.14066):** commitment
  game, generator, planners (Myopic / Upper / Lower value estimates),
  text-to-game pipeline with stability metrics (goal sim 0.791, action sim
  0.960). Primary model and benchmark.
- **Zhu, Wang, Subramanian & Poupart (2025, AISTATS), *Learning to Negotiate
  via Voluntary Commitment*:** commitment games with an incentive-compatibility
  constraint on proposals. Formal basis for our acceptance rule (an offer is
  predicted accepted if the opponent's value does not fall).
- **Wu et al. (2024, ICML), *Minimally Modifying a Markov Game*:** minimal
  payoff change that alters the equilibrium. We take the inverse question —
  smallest change to `G_opp` that flips an acceptance — as the basis for the
  per-offer margin (Prop. A4).
- **Braun, Auddy & Toussaint (2026, RLJ), *Trajectory First*:** constrained
  diversity (`max Diversity s.t. J ≥ α v*`). Used to define the strategy menu
  (§6.6).
- **Prompt sensitivity:** Sclar et al. (2024, arXiv 2310.11324), Mizrahi et
  al. (2024): meaning-preserving prompt changes move LLM outputs.
- **Behavioural testing:** CheckList (Ribeiro et al. 2020) — invariance (INV)
  tests. This plan is an INV study.
- **Self-consistency** (Wang et al. 2023): resampling the same prompt; our
  main control.
- **Ma et al. (2024, 2025):** negotiators want options with risks, not one
  directive → output is a menu.
- **LLM-as-judge biases:** Zheng et al. (2023), Panickssery et al. (2024).

---

## 3. Formalisation

**Package.** `P = (D, R_us)`: shared documents and our private role card.

**Rewording set.** `[P]`: all accepted rewordings of `P` (§1.2). `ν`: the
sampling distribution over `[P]` induced by our operators.

**Assumption M (meaning preserved).** Every `P′ ∈ [P]` describes the same
true game `𝔊* = (A, goals, 𝒞, types, G*)`. Holds only as well as the
acceptance filter; if it fails, measured brittleness is an upper bound.

**Game** (Benac form, two players):
- Commitment state `C ∈ {0,1}^{|A_us|+|A_opp|}`, starts at `C⁰ = 0`, entries
  only go 0 → 1.
- Goal satisfaction: linear `S_g(C) = |𝒞_g ∩ C| / |𝒞_g|`; all-or-nothing
  `S_g(C) = 1[𝒞_g ⊆ C]`. Both are non-decreasing in `C`.
- Rewards `r_i(C) = Σ_g G_{g,i} S_g(C)`.
- Protocol: `T` turns, proposer alternates, at most `k` new commitments per
  side per offer, accept/reject, walk-away allowed.
- Acceptance model: the opponent accepts `C → C′` iff its estimated value
  does not fall, `Σ_g Ĝ_{g,opp} ΔS_g ≥ 0` (Zhu et al. IC constraint).

**Pipeline as a map.** `Ĝ(P′)`: game built from text. `σ(Ĝ)`: planner output
(deterministic). `adv(P′, Ĝ, σ)`: advisor output (stochastic).

**Plan** `σ`: ordered offers, expected responses, fall-backs, walk-away
point, ethics flags, and a margin per offer (Prop. A4).

**Objective.** `U(σ) = r_us(σ; 𝔊*)`, normalised to `[0,1]`, scored on the
**true** game. Brittleness is any dependence of `σ` or `U(σ)` on which
`P′ ∈ [P]` was read.

---

## 4. Package → commitment game

| Step | Input → output | Notes |
|---|---|---|
| 0 Ingest | PDF/docx → items with verified quotes | reuse `../pipeline/` |
| 1 Atomise | items → facts `F` with quote, type, relevance | new |
| 2 Players | `us`, `opp`; others → stakeholders | stakeholders become goals/constraints |
| 3 Actions | `F` → `A_us`, `A_opp` | concrete commitments, owner + quote, ≤ ~8 per side |
| 4 Goals | `F` → goals with `𝒞_g` and type | costs as goals with negative value |
| 5 `G_us` | role card → our column | repeated elicitation, median |
| 6 `π(G_opp)` | shared docs + role-card statements → distribution | spread from repeated elicitation |
| 7 BATNA | `r(C⁰)` + outside options | |
| 8 Checks | Benac stability metrics, human check, round trip on generated games | |

**Worked sketch — Sim 2 (us = Camp Commander, opp = FWB). Numbers
illustrative.**

Actions — CC: `a1` independent FWB distribution staff · `a2` FWB hires local
labourers · `a3` stop giving refugee rations to guards · `a4` MASHA/monitor
access · `a5` guard conduct code + complaint channel. FWB: `b1` ongoing food
deliveries · `b2` separate ration / cash-for-work for guards · `b3` fuel and
sanitation support · `b4` joint distribution with CC's office · `b5` no
public criticism while the deal holds.

| Goal | `𝒞_g` (type) | G_us | G_opp |
|---|---|---|---|
| g1 Refugees adequately fed | {b1, a3} (AoN) | 2 | 10 |
| g2 Guards fed and loyal | {b2} | 9 | −1 |
| g3 CC visibly in charge | {b4} | 6 | −1 |
| g4 Independent outsiders in camp | {a1, a2} (lin) | −5 | 4 |
| g5 No unrest / international incident | {b1, b2, a5} (lin) | 7 | 5 |
| g6 Aid independent, not diverted | {a1, a3, a4} (lin) | −3 | 9 |
| g7 Camp infrastructure works | {b3} | 5 | 0 |
| g8 FWB spends beyond food mandate | {b2, b3} (lin) | 0 | −3 |

10 actions → 1,024 states → exact search. The trade-off table surfaces the
logroll `b2 ↔ a3` (guards fed separately; diversion ends).

**Rewording enters before step 1** (whole package) or **between steps 1 and
3** (fact level). Both are run; the fact-level version allows attribution
to individual facts.

---

## 5. Rewording engine

1. Embed every fact and document with one open sentence encoder (MTEB-class).
2. Generate `K` rewordings per unit with an LLM, at several requested
   "distances" (light / moderate / heavy rewording) so `d_emb` covers a range.
3. Accept per §1.2; log rejection rates per operator.
4. Record `d_emb(P, P′)` (cosine distance, mean over changed units).
5. **Random-noise control** (for H2): character/word noise at matched
   `d_emb` that is *not* checked for meaning — separates "meaning-preserving
   wording" from "any surface change".

---

## 6. Components

### 6.1 Extractor + atomiser — §4 steps 0–1.
### 6.2 Rewording engine — §5.
### 6.3 Game builder — §4 steps 2–8.
### 6.4 Planner (non-LLM)
Exact search over commitment sequences (small games); MCTS with Benac value
estimates for larger ones. Outputs plan, trade-off table, and the margin of
every offer (Prop. A4).
### 6.5 Strategic advisor and ethics advisor (LLM)
Review the plan for things `G` leaves out; ethics flags (humanitarian
principles, do-no-harm) with veto. Write the brief.
### 6.6 Aggregator
Combine `K` readings:
- **Game-level:** average `Ĝ` over rewordings (when structure matches), then
  plan once.
- **Plan-level:** majority over plan archetypes; report agreement rate.
- **Stability label:** the plan is "stable" if Prop. A4's certificate holds
  for all `K` readings.
- **Menu:** 3–5 plans maximising diversity subject to
  `U(σ_i) ≥ α · max U` (Braun et al. constrained diversity).
### 6.7 Opponent simulators and executor
Planner opponents and LLM opponents (≥ 2 model families) play the plan in
the turn-based game, for scoring.
### 6.8 Judge
Programmatic scoring from the true `G` where available; cross-family LLM
judge for unscored packs, order-swapped, calibrated against human ratings.

```
 package P ──► rewording engine ──► P′_1..P′_K
                                      │
                         extractor + game builder ──► Ĝ_1..Ĝ_K
                                      │
                                   planner ──► σ_1..σ_K (+ margins)
                                      │
                   strategic + ethics advisors ──► reviewed plans
                                      │
                                 aggregator ──► brief + menu + stability label
```

---

## 7. Formal results

Notation: `ν` over `[P]`; `Ĝ(P′)`; `G*` the true matrix; `U ∈ [0,1]`.

**Prop. A1 (Rewording spread lower-bounds extraction error).**
`E_ν‖Ĝ(P′) − G*‖² = ‖E_ν Ĝ − G*‖² + E_ν‖Ĝ − E_ν Ĝ‖²`, hence
`E_ν‖Ĝ − G*‖² ≥ E_ν‖Ĝ − E_ν Ĝ‖²`.
*Proof.* Expand around `E_ν Ĝ`; the cross term has expectation zero. ∎
*Use.* On real packs there is no gold `G`. The rewording spread is
measurable and is a guaranteed lower bound on the error.

**Prop. A2 (When aggregating over rewordings helps).**
Let `Ḡ_K = (1/K) Σ_k Ĝ(P′_k)`. If per-entry errors have common variance
`s²` and pairwise correlation `ρ`, then
`E‖Ḡ_K − G*‖² = ‖bias‖² + s² · (ρ + (1−ρ)/K)` (per entry, summed).
*Proof.* Variance of the mean of `K` equicorrelated variables:
`(1/K²)(K s² + K(K−1) ρ s²)`. ∎
*Use.* Aggregation removes wording variance, not bias. At equal `K`,
rewording beats same-text resampling iff `ρ_reword < ρ_resample` (with equal
bias). This is the exact form of H4, and `ρ` is estimated from data.

**Prop. A3 (Errors in our own column have bounded cost).**
For every `C`: `|r_us(C; G_us) − r_us(C; G′_us)| ≤ ‖G_us − G′_us‖₁ =: ε`.
*Proof.* `S_g ∈ [0,1]` and the triangle inequality. ∎
*Corollary.* If the set of plans the opponent is predicted to accept is the
same under both, the plan chosen under `G′_us` loses at most `2ε` on the
true values: `r(σ′) ≥ r′(σ′) − ε ≥ r′(σ*) − ε ≥ r(σ*) − 2ε`. ∎

**Prop. A4 (Acceptance margin).**
For an offer `C → C′` with `ΔS_g = S_g(C′) − S_g(C)` and margin
`m = Σ_g G_{g,opp} ΔS_g > 0`, acceptance is unchanged for every `δ` with
`‖δ‖₁ < m / ‖ΔS‖_∞`; the bound is tight.
*Proof.* Hölder: `|δ·ΔS| ≤ ‖δ‖₁ ‖ΔS‖_∞`. Tightness: put all mass on
`argmax_g |ΔS_g|` with opposite sign. ∎

**Corollary A4′ (Plan stability certificate).**
For a rewording, let `ε_us = ‖ΔĜ_us‖₁`, `ε_opp = ‖ΔĜ_opp‖₁`, and
`m_min = min` over offers in the planner's search of `m / ‖ΔS‖_∞`. If goals
and actions are unchanged, `ε_opp < m_min`, and the chosen plan beats the
runner-up by more than `2 ε_us`, the planner returns the same plan.
*Proof.* By A4 the feasible plan set is unchanged; by A3 the argmax is
unchanged. ∎
*Use.* A deterministic, checkable stability statement in `G` space, shown
in the brief. *Limit:* says nothing when rewording changes the game's
structure; structure stability is measured separately (Benac metrics).

**Prop. A5 (Winner's curse).** With noisy scores `Ŝ_i = S_i + ε_i`,
`ε_i` σ-sub-Gaussian over `N` candidates, `î = argmax Ŝ_i`:
`E[Ŝ_î − S_î] ≤ σ √(2 ln N)`. *Use:* re-score any selected plan on fresh
episodes.

**Prop. A6 (Sample size).** For scores in `[0,1]`, `n ≥ 2 ln(4/δ) / Δ²`
episodes per strategy separate a true gap `Δ` with probability `1 − δ`
(Hoeffding + union bound). `Δ = 0.1, δ = 0.05 → n ≈ 876`; paired designs
need fewer.

**Measure (not a theorem): embedding effect.**
`L̂ = max_{P′} D(σ(P), σ(P′)) / d_emb(P, P′)` and `corr(D, d_emb)`. Ideal:
`D ≡ 0`. Report per stage (game, plan, advisor).

---

## 8. Evaluation

### 8.1 Studies
- **S1 Brittleness by stage.** For each pack/game and `K` rewordings,
  measure change at: game structure (Benac similarity), `G` entries (L1),
  plan (structured diff), advisor output (archetype flip, rationale
  distance). Advisor-only variant: fix `Ĝ`, reword only the advisor's input.
- **S2 Embedding effect.** `D` vs `d_emb` curves; `L̂`; rewording vs
  random-noise control at matched `d_emb`.
- **S3 Aggregation.** Regret on generated games (true `G` known) for:
  single reading, same-text resampling × K, rewording × K. Estimate `ρ`
  (Prop. A2).
- **S4 Certificate validity.** How often Corollary A4′ holds, and whether
  certified plans are in fact stable on fresh rewordings.

### 8.2 Hypotheses
- **H1 (brittleness exists):** a single-reading pipeline changes its plan
  under accepted rewordings at a non-trivial rate.
- **H2 (wording, not just noise):** brittleness under meaning-preserving
  rewording is comparable to random noise at matched `d_emb` (i.e. the
  system reacts to surface form).
- **H3 (stage):** most plan changes come from `Ĝ_opp` near acceptance
  thresholds (predicted by A3/A4).
- **H4 (aggregation):** rewording × K lowers regret and instability versus a
  single reading, and versus same-text resampling × K.
- **H5 (planner helps):** the planner pipeline is less brittle than an
  LLM-only advisor.

### 8.3 Baselines (compute-matched)
| ID | Condition |
|---|---|
| B0 | Single LLM, zero-shot strategy |
| B1 | B0 + chain-of-thought |
| B2 | Same-text resampling × K, aggregated |
| B3 | Multi-agent, single reading |
| B4 | Random-noise perturbation × K (matched `d_emb`) |
| B7 | Planner on single-reading `Ĝ`, no LLM advisors |
| B8 | LLM advisors only, no planner |
| **A** | Rewording × K + planner + advisors + aggregator |

### 8.4 Metrics
Plan-change rate; archetype flip rate; `L̂`; L1 in `G`; Benac goal/action
similarity; our utility and regret on generated games; agreement rate;
walk-aways below BATNA; certificate coverage; ethics-flag stability.

### 8.5 Statistics
Paired designs, mixed-effects (condition fixed; pack, opponent random),
bootstrap 95% CIs, Holm–Bonferroni, ≥ 3 seeds.

---

## 9. Risks
| Risk | Mitigation |
|---|---|
| Rewordings secretly change meaning (Assumption M fails) | NLI both ways + hard-fact freeze + 5% human check; report as upper bound |
| Rewording changes game *structure* (new/missing goals) | Report structure stability separately; A4′ applies only when structure matches |
| Aggregation helps only as much as resampling | That is a valid finding (H4 false); report it |
| Judge bias | Programmatic scoring on generated games; cross-family judge |
| Cost | Prompt-hash cache; small `K` pilots |

---

## 10. What to build and timeline (≈8 weeks from 2026-10-20)

| Wk | Deliverable | Check |
|---|---|---|
| 1 | Repo skeleton, schemas, LLM client + cache, extractor + atomiser | Sim 1/2 extract; quotes 100% verified |
| 2 | Game builder; Sim 2 game; Benac generator + game→text renderer | Rendered package round-trips to same `G` |
| 3 | Planner (exact) + trade-off table + margins; rewording engine + filter | ≥ 95% of accepted rewordings human-judged meaning-preserving |
| 4 | Advisors, aggregator, opponents, judge | Full episode runs end to end |
| 5 | S1 + S2 | Brittleness-by-stage table, `D` vs `d_emb` plots |
| 6 | S3 + S4 | Aggregation vs resampling with CIs; certificate coverage |
| 7 | Freeze + exercise pipeline (brief ≤ 6 min) | 10/10 timed dry runs |
| 8 | Write-up | Reproduce headline numbers |

---

## 11. What this plan can and cannot claim
- **Can:** quantify wording brittleness at each stage; give a provable
  stability certificate in `G` space; show whether aggregating rewordings
  beats resampling.
- **Cannot:** say whether advice responds correctly when facts *really*
  change, or discover strategies for situations not in the package. That is
  Plan B.
