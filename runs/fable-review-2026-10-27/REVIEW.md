# Review: Perturbation-Robust Negotiation Advisor (2026-10-27)

Reviewer: Claude Fable 5.1, working from `FABLE_REVIEW_PROMPT.md`. Branch `feature/live-advice-model` at `531c8d0` plus uncommitted live-advice work. Evidence: code, `runs/`, `results/`, `.data/analysis.sqlite`, `data/negotiation-workspace.json`, git history, and a 22-call pilot on the Qiso pack (section 8). Tests: `pytest -q tests` 59 passed; `node --test tests/*.test.js` 40 passed.

## 1. Verdict

No. The current build cannot show whether meaning-preserving rewordings change the recommendations, for three independent reasons. First, the only recommendation that is ever compared across readings is the plan from the teammates' rule-based builder and solver, which make no model calls, so once the extracted facts are fixed the "recommendation" is a deterministic function of regex matches and list order (`game_builder.py:140-287`, `solver.py:10-159`). A "changed" outcome there measures whether a paraphrase flipped a regex, not whether model-estimated games are brittle. Second, the fact-level job rewords the 16 highest-weighted facts, and that weighting prefers constraints and role-card context, which the builder never turns into actions; in the live Qiso run 0 of the 16 reworded facts were action facts, so its 128 of 128 "stable" results were guaranteed before any model call (`backend/engines.py:175-176`). Third, there is no same-text control (B2): both caches return the identical answer for an identical input, and the document-level job's "fresh baseline extraction" is a cache hit of the original extraction, so sampling variance has never been measured. The rewording engine itself is in good shape (filter rejected 12 of 12 meaning-changing probes; 76 to 79 of 81 fact paraphrases accepted; `d_emb` rises with requested strength), but no human audit has been done and the document-level path has never run on real data. The shortest credible path is to measure a recommendation that actually depends on the model, under rewording × K versus same-text × K at equal compute: either the model-written brief (which the team already uses) or a model-built game (the stashed builder is the closest prior art). The pilot in section 8 does exactly this at small scale: three same-text runs of the brief produced two opening archetypes and three fallback archetypes, and the reworded runs fell inside that spread, so without B2 any "the brief changed under rewording" result would have been a false positive.

## 2. Plan-vs-build table

Status: **done**, **partial**, **placeholder**, **missing**, **deviates**. Impact = effect on the main research question (RQ).

| Plan item | Status | Evidence | Impact on RQ |
|---|---|---|---|
| §5.0 Ingest (PDF/DOCX → text with locations) | done | browser PDF.js/Mammoth; `backend/inference.py:322-399` quote verification | neutral |
| §5.1 Atomise (model extraction with verbatim quotes, category, subject, force, modality) | done | `backend/inference.py:25-37, 61-73, 322-399`; 487 verified facts in the Qiso export | neutral; this is the only model stage before the game |
| §5.2 Players / stakeholders | partial | case synthesis infers `our_side`/`opponent` (`inference.py:38-44`); builder uses `parties` strings and `subject` matching (`game_builder.py:197-227`) | low |
| §5.3 Actions (`A_us`, `A_opp`, ≤8 per side, owner + quote) | placeholder | category/regex rules, owner from `subject` then party mention then alternation (`game_builder.py:140-194`); Qiso: 4 actions, all opponent-owned | **harmful**: not model-dependent; owner alternation is order-dependent |
| §5.4 Goals with `𝒞_g` and type | placeholder | one all-or-nothing goal per action plus joint pairs matched by list order (`game_builder.py:256-281`) | **harmful**: pairing by order makes "game changed" fire on re-ordering |
| §5.5 `G_us` from role card (repeated elicitation, median) | placeholder | constants −1/+2/+3 (`game_builder.py:259-262, 278-279`) | **harmful**: H3, Props A2–A4, S3, B9 untestable |
| §5.6 `π(G_opp)` as a spread | placeholder | one extra column `lower-joint-benefit` with joint value 1 (`game_builder.py:282-286`) | **harmful** |
| §5.7 BATNA / outside option | missing | `r(C⁰)=0`; `walkAway` is text only (`solver.py:95, 136-149`); plan §18.5 warns about exactly this | harmful for utility/regret metrics |
| §5.8 Checks (Benac stability, round trip) | missing | — | needed for S1 structure metrics |
| §6 Rewording operators (4) at 3 levels | done (CLI), partial (app) | `negotiator/reword/operators.py`; app fact job uses `light` only (`engines.py:170`); app doc job uses 2 ops × 3 levels (`engines.py:222`) | S2 impossible from the app path |
| §6 Acceptance filter (cosine, two-way NLI, hard facts) | done | `filter.py:127-143`; probes in section 4 | good; red lines not covered (`CLAUDE.md` §9 admits it) |
| §6 `d_emb` stored per rewording | done | `filter.py:140`, `engine.py:29` | neutral |
| §6 Random-noise control (B4) | partial | `noise.py` generates matched noise; disabled in app (`engines.py:138`); never run through builder/solver | H2 unmeasured |
| §3.2 5% human audit (≥95% meaning-preserving) | **missing** | `human_review_sample.jsonl` in every run has no judgement field | Assumption M unverified; Week 3 gate not passed |
| §6.4 Planner: exact search, trade-off table, margins | partial | our offers only, myopic accept rule, no alternation, no margins, no trade-off table (`solver.py:51-84`); stash `planner.py` has alternation + margins + certificate | S4 untestable; ties undetected |
| §6.5 Strategic advisor reviewing the plan | deviates | the model brief is produced *before* and independently of the game (`inference.py:52-58, 428-632`) | the user-facing recommendation is outside the measured pipeline |
| §6.5 Ethics advisor with veto | missing | placeholder strings (`solver.py:130, 144`) | ethics-flag stability unmeasurable |
| §6.6 Aggregator: averaged game, pool, re-score, menu, fresh re-scoring | missing | — | H4, H6, S3, S5 blocked |
| §6.6 Contingent tree; §24 QD archive; Vendi | missing | — | H6 blocked |
| §6.7 Opponent simulators / executor | missing | — | regret unmeasurable |
| §6.8 Judge | missing | — | — |
| Benac generator + game→text renderer (Week 2) | missing | — | no true `G`; S3/S5 blocked |
| S1 brittleness by stage | partial | game/plan stage only via `game_signature`/`plan_signature` (`engines.py:44-54`) on a placeholder game | see section 3 |
| S2 embedding effect | partial | `d_emb` recorded; no `D` vs `d_emb` curve on any recommendation | — |
| S3, S4, S5 | missing | — | — |
| B2 same-text × K (main control) | **missing** | caches key on text/prompt (`inference.py:238, 181`; `negotiator/llm.py:41-44`); only the CLI `--seed` can create a replicate | **harmful**: RQ unanswerable without it |
| B4 noise × K | partial | texts generated, never evaluated | — |
| B9 opponent-utility sampling | missing | no `π(G_opp)` to sample | — |
| B0/B1/B3/B7/B8 | missing | — | — |
| §9.3 metrics | partial | stable/sensitive/changed only; no L1, similarity, regret, agreement, certificate coverage | — |
| §18.3 structured live events, confirmation, undo | done | session export shows 9 confirmed events, 0 commitments | neutral |
| §18.4 belief update, re-plan, next-move card | missing | rule-based template in `live-strategy-worker.js` | neutral to RQ |
| §18 "no LLM in live loop" | **deviates** (uncommitted) | `POST /api/live/advice`, `AnalysisService.live_advice` (`inference.py:280-320`) | justified operationally (rule template repeated 9×), neutral to RQ as long as it is not the measured recommendation; label it in the write-up |
| §20.3 P0 one package-to-game path + source-linked brief | partial | path exists but game is placeholder | — |
| §20.3 P0 validated rewordings + same-text control | half | rewordings yes; control no | **blocking** |
| §20.3 P0 timed cutoff, printed fallback, structured entry | done | `PIPELINE_INTERFACE.md`; browser tests | neutral |
| §20.3 P1 alignment, pool, re-score, robust fallback | missing | `align_facts` exists for doc path only (`engines.py:320-332`) | — |
| §20.3 P1 belief update, contingent branches | missing | — | — |
| Model-based builder (prior art) | shelved | `stash@{0}`: `negotiator/game/builder.py` (atomise/structure/elicit), `planner.py` (alternating, margins, A4′ certificate), prompts; output in `runs/game-sim2` (10 actions, 218 facts, plan with margins) | closest existing implementation of §5 steps 2–8 and §6.4 |

Document conflicts to flag (plans win over `CLAUDE.md`, per its own rule): `Detailed_Plan.md` §3.2/§5 confirm fact-level rewording *after* atomisation as the experiment and defer `paraphrase_doc`/`reorder`; `CLAUDE.md` §2 and `README.md` §3.2 run both entry points. The build follows `CLAUDE.md`. `Detailed_Plan.md` §21.1 also says register/order changes "can alter pragmatics" and should be excluded from the primary invariance analysis unless audited. Decide and record which it is.

## 3. Threats to validity (ranked)

1. **The compared recommendation does not depend on the model.** Given fixed facts, `build_game` + `solve` are deterministic rules. Probe (section 4): rewording "FWB can provide rice." to "Both FWB and the camp agree FWB provides rice." flips the `AGREEMENT`∧`JOINT` regex and yields "changed"; "FWB is able to supply rice." is "stable". So the current stable/sensitive/changed rates are a property of `game_builder.py`'s regexes, not of LLM game inference. *Fix:* measure a model-dependent recommendation: (a) the brief's structured fields, or (b) a model-built game (re-apply `stash@{0}` builder; elicit `G` columns per reading).
2. **Unit selection excludes the facts that matter.** `engines.py:175-176` weights `constraint` 8 and role-card +12; `game_builder.py:145` skips every constraint and `_actions` only admits `commitment|resource|timeline|goal`. On Qiso the 16 selected facts were 9 context, 5 constraint, 1 resource, 1 goal, 14 from the role card, 0 of 4 action facts; all 128 variants "stable". *Fix:* select action-eligible facts (and facts the brief cites), stratified by category; report which facts were perturbed.
3. **No same-text control; caches guarantee zero variance.** `artifact()` keys on `{scope, version, provider, model, kind, schema, inputs}`; `_request` keys on body; `negotiator/llm.py` keys on prompt+schema+model+effort+seed, and only the CLI exposes `--seed`. `engines.py:239, 249` labels the original's extraction a "fresh" baseline, but `self.analysis.document(source)` on unchanged text is a cache hit (confirmed: 45 document calls in the ledger = 28 Qiso + 17 Sim 2 sources; zero re-extractions). *Fix:* explicit replicate policy (scope or seed per replicate) for every model stage; count it in the compute budget.
4. **Order artefacts are counted as changes (document path).** Joint goals pair `ours[i]` with `theirs[i]` by list order (`game_builder.py:272`); `_owner` alternation (`game_builder.py:194`); solver tie-break follows action bit order (`solver.py:56, 64-79, 182-192`) and candidate sort is stable on insertion order (`solver.py:133`). Probe: swapping two FWB facts changed both game and plan signatures with identical facts. Re-extraction returns facts in model order, so the doc path will report spurious "changed". `align_facts` (`engines.py:320-332`) is greedy at cosine ≥ 0.85, so a legitimately rephrased claim below 0.85 stays unmatched and counts as a change. *Fix:* order-invariant goal construction and signatures; alignment by quote overlap first, embedding second; report unmatched facts separately.
5. **Outcome definitions ignore ties and equivalence.** `plan_signature` compares only `strategies[0]`'s steps (`engines.py:51-54`); equal-value plans differing only in tie-break are "changed"; no utility tolerance; "sensitive" means any constant in `G` or any owner changed. The plan requires three levels: different text, different structured action, materially different decision quality (§21.1). *Fix:* compare outcome profiles `S(C)` and value within tolerance (the stash planner already does this), and keep an "equally good alternative" bucket.
6. **Perturbation validity is unaudited.** Filter is strict on single sentences (section 4) but: no human judgement exists for any sample; red lines are not in the hard-fact check; register changes pragmatics; all K candidates for a unit come from one call with `seed=0` (`engine.py:23`), so they are not independent; doc-level NLI uses 1–3-sentence windows and the top-3 nearest windows (`filter.py:94-122`), so a dropped condition inside a long sentence can pass if the rest entails. *Fix:* run the Week 3 audit on the existing `human_review_sample.jsonl` files (15 items exist now), add red-line tokens to the hard-fact set, one seed per candidate.
7. **The recommendation users saw is never perturbed.** The brief (opening, fallback, red lines, issues, trades) comes from `parse()`; nothing compares briefs across readings. The live run's advice came from this brief and, later, from the uncommitted live-advice call. *Fix:* section 6 design; the pilot (section 8) shows it is feasible at low cost.
8. **Dev/test contamination.** The Qiso pack was the live test (plan §10, §21.1) and is now in `data/` being used to develop the live-advice prototype. Any numbers tuned on it are development numbers.
9. **Doc-level rewording may truncate.** `_gateway_llm` routes rewording through `_request`, whose output budget for an unknown task kind is 4,500 tokens including thinking (`inference.py:162`); two heavy rewrites of a 4k-character document plus thinking can exceed it, which raises `InferenceError` and fails the whole job (`engines.py:241-244` propagates). Suspected, not observed, because the path has never run.
10. **Equal-compute accounting is absent.** Document rewording adds one extraction per accepted rewording; fact rewording adds none. Neither job records tokens per condition.

## 4. What existing evidence shows

Recomputed from `runs/*/rewordings.jsonl` (all `claude-opus-5-5`, `seed=0`, `tau=0.85`, NLI 0.5):

| Run | Units | Operator | Candidates | Accepted | Rejections | Median `d_emb` light / moderate / heavy |
|---|---|---|---|---|---|---|
| bench-facts | 9 | paraphrase_fact | 81 | 79 (98%) | cosine 2 | 0.033 / 0.049 / 0.082 |
| sim2-facts | 9 | paraphrase_fact | 81 | 76 (94%) | cosine 2, nli_fwd 1, nli_bwd 2 | 0.019 / 0.044 / 0.063 |
| bench-docs | 3 | paraphrase_doc | 18 | 13 (72%) | nli_fwd, hard_facts | 0.0023 / 0.0040 / 0.0086 |
| bench-docs | 3 | register | 18 | 10 (56%) | nli_fwd 5, hard_facts 2, nli_bwd 1 | 0.0036 / 0.0085 / 0.032 |
| sim2-docs | 16 | paraphrase_doc | 96 | 64 (67%) | nli_fwd 23, nli_bwd 7, hard_facts 2 | 0.0038 / 0.011 / 0.051 |
| sim2-docs | 16 | register | 96 | 51 (53%) | nli_fwd 33, nli_bwd 5, hard_facts 5, cosine 2 | 0.0080 / 0.021 / 0.060 |
| pilot-opus55 | 1 | both | 12 | 1 | nli 7, hard_facts 4 | — |

- `CLAUDE.md` §9 reports bench-docs as 11/18 and 9/18; the files say 13/18 and 10/18 (the name-check fix in `f630e16` likely post-dates the note).
- Requested strength raises `d_emb` monotonically in every run (confirmed).
- Noise control matching: median |`d_noise` − `d_reword`| = 0.0022, max 0.023 on sim2-facts; the matched texts were never evaluated downstream.
- The sim2-facts rejections are mostly Security Log lines where the NLI reads "without permission"/"without approval" or a clause reordering as non-entailment; one `cosine` rejection at 0.835 is a plausible paraphrase (false reject).
- **Human audit:** 4+4+1+6+1 sampled items exist across runs; none carries a judgement. The ≥95% gate has not been attempted.
- **Filter probes (this review, local models only):** 12 meaning-changing edits (negation, must→may, authorised→not authorised, all→some, attribution swap, dropped condition, flipped condition, red line→concern, date, 22→20, one→two trucks, might→has) were all rejected; a genuine paraphrase and "Prof→Professor" were accepted. The brief's listed residual "Prof→Professor" rejection no longer reproduces.
- **Qiso live run (`data/negotiation-workspace.json`):** 28 sources, 487 facts, 4 actions all owned by the Mayor, one strategy "Walk away", 128 variants all `stable`, 0 action facts reworded (section 3, item 2). This is not evidence of robustness.
- **Model-call ledger (`.data/analysis.sqlite`, all 2026-10-26, Opus 5.5):** 45 document, 4 case, 24 rewording, 1 live-advice calls; 224,570 input and 183,925 output tokens. No document-level re-extractions ever occurred. The brief's "about $1.50" for the Sim 2 rehearsal cannot be checked from the files; the gateway quota showed $277.39 of $300 remaining before this review's pilot, so total October spend before the pilot was $22.61 across all runs.
- **Sim 2 "No improving offer → Walk away"** is not in any saved export; it is an anecdote consistent with the builder's behaviour on Qiso.
- `runs/game-sim2` (stashed model builder, 2026-10-23): 218 verified facts, 10 actions on both sides, an 8-turn plan with margins and fallbacks. It is the only artefact where a game with a two-sided action set and non-constant `G` was produced from a course pack.

## 5. Bugs that bias results (correctness only)

1. `backend/engines.py:175-176` fact selection weights prefer categories the builder discards; action facts are never reworded in practice. Direction: toward "stable".
2. `game_builder.py:272` and `:194`: joint-goal pairing and fallback ownership depend on fact order. Direction: toward "changed" in any path where fact order can differ (doc path).
3. `solver.py:56, 182-192, 133`: tie-break and candidate order depend on action order; `plan_signature` compares only the top option. Direction: toward "changed"; ties invisible.
4. `backend/engines.py:239, 249-251`: the "fresh" baseline extraction is a cache hit of the original. Direction: understates same-text variance to exactly zero.
5. `backend/engines.py:170`: app fact job forces `levels=['light']`; `d_emb` range collapses, so any S2 curve from the app is a point.
6. `backend/engines.py:320-332` `align_facts`: unmatched below cosine 0.85 → new fact id → "changed" regardless of content. Direction: toward "changed".
7. `backend/inference.py:162`: rewording through the gateway path gets a 4,500-token output budget including thinking; long documents at `heavy` may truncate and fail the job (suspected).
8. `negotiator/reword/engine.py:23`: one call per (unit, operator, level) returns all K candidates; candidates are correlated samples. Direction: understates variance across readings.
9. `backend/engines.py:138`: noise disabled in the app; `noise.py` output is never scored. B4 cannot be computed from any saved run.

10. `backend/inference.py:173-175`: the Bedrock request body has no structured-output `format`, unlike `negotiator/llm.py:51`; in the pilot 1 of 7 case calls returned unparseable JSON at `end_turn` and the reading was lost under the no-retry policy. Direction: random loss of readings; also wastes budget.

Not bugs but worth knowing: `hard_fact_diff` treats a capitalised token as common if its lowercase form appears anywhere in either text (`filter.py:70`), so "Mayor"→"Governor" is caught only as an added name, and a lost name that also occurs lowercase is not flagged; NLI then has to catch it.

## 6. Minimal experiment design for the main question

**Question.** Does rewording × K change (and, aggregated, improve) the recommendation more than same-text × K at equal compute?

**Recommendation to measure.** Two layers, reported separately:
- *Layer A (primary, scoreable):* the plan from a **model-built game**. Re-apply the stashed `negotiator/game/builder.py` (atomise once; `structure` + `elicit` per reading) and the stashed `planner.py` (alternating proposer, margins, outcome-profile equivalence). Keep the teammates' `game_builder.py` as baseline B7′ ("rule-based builder") so the comparison also tests H5-style "does a model builder add brittleness".
- *Layer B (what users see):* the structured brief from `parse()`: opening, fallback, alternatives, red lines, our constraints, issue titles, trade-offs. Compare with embedding similarity plus a cross-family or separate-call judge that assigns strategy archetypes. This layer cannot be scored for quality, only for stability.

**Perturbation sets.** Fact-level `paraphrase_fact` at three levels after atomisation (the plan's confirmed entry point), K=4 pilot, K=8 final; original fact set as the single reading. Reword only facts that enter the builder (actions, goals, constraints, role-card facts). Document-level and register as a secondary, audited extension only.

**Controls.** B2: same facts, K independent builder runs (seed or scope per run; no cache reuse across replicates). B4: noise at matched `d_emb`, K runs (H2, secondary). B9 only if `π(G_opp)` elicitation exists (it does in the stash: `elicit` returns n samples).

**Packs and games.** Sim 1 and Sim 2 for development; 10–20 generated commitment games rendered to text as the scored set (a templated renderer from `G`, actions and goals is a one-day task; the Benac generator can follow). Hold out whole games. Qiso is the test case study; do not tune on it.

**Metrics.** Per game and condition: plan-change rate with an equivalence tolerance (outcome profile `S(C)` and value within ε), structure similarity (best-match cosine of action/goal labels, as Benac et al. do: 0.960 actions, 0.791 goals on their own pipeline), L1 in aligned `G`, regret against the true-`G` optimum on generated games, estimated `ρ` (Prop. A2) from within-condition correlations, agreement rate, archetype flip rate (layer B). Statistics: paired per-game differences, bootstrap over games (not over paraphrases), ≥3 seeds for B2 and the single reading, Holm correction over H1/H2/H4 only.

**Budget (per generated game, K=4, 3 seeds where sampling matters).** Builder calls: structure 1 + elicit 2 = 3 per reading; readings = 1 single + 4 B2 + 4 RW = 9 (+4 B4) → 27–39 calls; rewording generation 3 calls (one per level returning K fact sets); total ≈ 30–42 calls, ≈ 150k input and 60k output tokens per game. 15 games ≈ 600 calls. Measured in this review: one Fable 5.1 case-synthesis call on a 6-document package cost about roughly $2 (22 calls, $20.63 total; see section 8) and took 170–350 s. At the measured Fable rate (~$1 per call averaged over the pilot), 600 calls is ~$600, more than twice the remaining $255. Use Sonnet 5.5 (or Haiku 5.5 for rewording generation) for the builder, elicitation and brief stages, reserve Fable/Opus for the judge, and record model IDs per stage. Shorter case prompts (the 128-claim synthesis input is ~32k tokens) would cut cost roughly in half.

## 7. Prioritised task list

| # | Priority | Task | Exit check | Owner | Plan week |
|---|---|---|---|---|---|
| 1 | P0 | Replicate policy: add `seed`/`replicate` to `AnalysisService.artifact` cache keys and to the engine jobs; same-text × K job (B2) | repeating with a new replicate makes a new call; K runs of identical facts produce K stored games/briefs | Vedant | 3 |
| 2 | P0 | Reword the right units: select action-eligible and brief-cited facts; expose all three levels in the app job; record which facts were perturbed | on Qiso ≥ 1 action fact is reworded per run; `d_emb` spans three bands | Vedant | 3 |
| 3 | P0 | Human audit of accepted rewordings: judge the 16 existing sample items plus a stratified sample per operator and level (≥ 60 items) | ≥ 95% judged meaning-preserving, or `tau`/NLI retuned and re-audited | Vedant (+ one teammate as second judge) | 3 |
| 4 | P0 | Order-invariant game construction and signatures; outcome-profile equivalence with tolerance; "equally good alternative" bucket | shuffling fact order never changes `game_signature`/`plan_signature`; ties reported separately | teammate (game_builder/solver owner), spec from Vedant | 3 |
| 5 | P0 | Model-built game: re-apply stash builder (`structure`, `elicit`) behind the same package contract; keep rule-based builder as B7′ | Sim 2 yields actions on both sides and non-constant `G`; round trip on one rendered game | Vedant; teammate reviews contract | 2–4 |
| 6 | P0 | Brief-level comparison job: run `parse()` per reading and store structured brief fields; archetype judge in a separate call | pilot design (section 8) runs end to end from the UI/CLI with B2 | Vedant | 4 |
| 7 | P1 | Templated game→text renderer + 10–20 generated games with true `G` | rendered text round-trips to the same structure for ≥ 80% of games | Vedant | 2–5 |
| 8 | P1 | Noise control through the pipeline (B4) | B4 outcomes stored with matched `d_emb` | Vedant | 5 |
| 9 | P1 | Aggregator v0: averaged aligned `G`, pooled plans, cross-scoring `Ū`/worst case | regret on generated games for single / B2 / RW with bootstrap CIs | Vedant | 5–6 |
| 10 | P1 | Fix doc path: budget for rewording output tokens; alignment by quote overlap first; count re-extraction calls in compute | doc job completes on Qiso role card; extractions logged per condition | Vedant | 4 |
| 11 | P1 | Live loop: label the model live-advice as a deviation; keep rule-based card as fallback; add belief update only if time | brief and write-up state which advice was model-generated | Vedant + frontend teammate | 7 |
| 12 | P2 | Red-line tokens in hard-fact check; one seed per candidate | probe set in section 4 plus red-line edits all rejected | Vedant | 4 |

Tasks 4 and 5 touch `game_builder.py`/`solver.py`, owned by teammates: send them the ordering probe (section 4) and the contract change (per-reading `G` columns, `opponentReadings` as samples) rather than editing their files.

## 8. Pilot results

Design (files: `pilot.py`, `compare.py`, `pilot.sqlite`, `pilot_ledger.json`, `pilot_results.json`, `rewordings.jsonl`, `b2_r*.json`, `rw_*.json`, `fable-review.yaml`; `configs/default.yaml` and `.data/` untouched).

- **Pack:** Qiso, subset of 6 sources: the Officer role card plus the 5 shared documents most cited by the live brief (Processing and Transport Protocols, Official Message to the Mayor, Message from Central Border Authority, National News 1, Refugee Facility Requirements). Same subset in both arms.
- **Recommendation:** the structured brief from `AnalysisService.parse` with `requireDetailedBrief` (opening, fallback, alternatives, red lines, constraints, issue titles, trade-offs).
- **Model:** `us.anthropic.claude-fable-5-1` (served as `claude-fable-5-1`), Bedrock route, effort `low`, case budget 20k tokens. Bedrock exposes no seed; replicates are separate cache scopes (`fable-review-rc-r{n}`, `fable-review-case-r{n}`), so each is an independent sample. Shared documents were extracted once and reused by every run.
- **B2 (same text):** 3 runs, each re-extracting the role card and re-synthesising the case.
- **RW (reworded):** the role card reworded at document level (`paraphrase_doc`, k=2 × 3 levels, 3 calls); all 6 candidates passed the filter (`d_emb` 0.0007–0.0094, NLI ≥ 0.989 both ways). Four were taken (light, moderate, heavy, light); each was re-extracted and re-synthesised once.
- **Judge:** one separate Fable call clustering the 6 (opening, fallback) pairs, anonymised and shuffled, into strategy archetypes (`prompt_hash 258da620366e0eb2`).
- **Pre-spend estimate:** 22 calls, ≈145k input and ≈100k output tokens; no price was known for Fable. **Actual:** 22 calls, 254,269 input and 167,614 output tokens, **$20.63** by gateway quota delta ($277.39 → $255.06). Case synthesis ran 170–350 s per call. Under a 1:5 input:output price ratio that is roughly $2 per case call and $0.25 per document extraction; treat as an estimate.

**Outcome.** 6 of 7 briefs produced. `rw_1` (light rewording) failed: the model returned `end_turn` with JSON that does not parse (13,375 output tokens, no truncation, no simple bracket repair); the app's validator rejected it and, under the no-retry policy, the reading is lost. The app's Bedrock body sends no structured-output format (`backend/inference.py:173-175`), unlike `negotiator/llm.py:51`.

Pairwise similarity of brief fields (encoder `BAAI/bge-base-en-v1.5`; lists use soft Jaccard at cosine ≥ 0.80):

| Field | B2 vs B2 (n=3) | RW vs B2 (n=9) | RW vs RW (n=3) |
|---|---|---|---|
| Opening (cosine) | 0.848 (min 0.810) | 0.874 (min 0.828) | 0.890 (min 0.870) |
| Fallback (cosine) | 0.786 (min 0.750) | 0.782 (min 0.729) | 0.758 (min 0.751) |
| Objective (cosine) | 0.926 | 0.891 | 0.873 |
| Issues (soft Jaccard) | 0.43 (min 0.20) | 0.56 (min 0.20) | 0.59 (min 0.36) |
| Red lines (soft Jaccard) | 0.73 (min 0.57) | 0.48 (min 0.00) | 0.18 (min 0.00) |
| Trade-offs (soft Jaccard) | 0.31 | 0.23 | 0.15 |
| Alternatives (soft Jaccard) | 0.00 | 0.17 | 0.17 |

Judge archetypes (same call for all six):

| Run | Arm | Opening cluster | Fallback cluster |
|---|---|---|---|
| b2_r1 | same text | 1 "acknowledge, gather facts, propose two-week timeline" | 1 "phased sequencing via alternative sites" |
| b2_r2 | same text | 2 "acknowledge, state legal terms, request facts" | 2 "phased sequencing plus cost submission" |
| b2_r3 | same text | 1 | 3 "hold firm, invite cost submission only" |
| rw_2 (moderate) | reworded | 2 | 1 |
| rw_3 (heavy) | reworded | 1 | 1 |
| rw_4 (light) | reworded | 2 | 2 |

Reading:
- **The brief is not stable under identical input.** Three same-text runs produced two opening archetypes and three fallback archetypes; the role card was extracted into 17–18 claims each time and the issue lists overlap by only 0.43.
- **Rewording added no detectable extra change at this n.** Reworded briefs were as similar to the same-text briefs (0.874) as those were to each other (0.848); every judge cluster contains both arms. This is the H1-versus-B2 comparison the plan asks for, and at n=3+3 it is null.
- **Red lines are the one field that looks reworded-sensitive, and it is a metric artefact.** All six briefs contain the same six constraints (no undocumented non-citizens; whereabouts accounted for; security paramount; two-week deadline; compensation only at the Protocol rate; memo not to be shared). They are split into 3 or 4 items with different groupings, which the set metric penalises. Compare red lines at the clause level, not the item level.
- **Content drift is small but real in both arms:** trade-offs and alternatives vary in which 2–5 of the same pool of ideas appear (phased pickup, Mayor's lists as the register, forwarding documented costs, families transported together, continued emergency aid). None introduces an unsupported commitment.
- **What this does and does not show.** It shows that the model-written brief has substantial sampling variance, that a B2 control is mandatory before any brittleness claim, and that the pilot design is feasible end to end in ~40 minutes for ~$20. It does not show that rewording is harmless: n is tiny, the perturbation was one document at `d_emb` ≤ 0.01, and no quality scoring exists for the brief. It also shows the cost problem: at Fable prices the full design in section 6 is unaffordable; use a cheaper model for the builder/brief stages or the Fable budget only for the judge.

## 9. Where this brief was wrong

- Benchmark numbers: the run files give `paraphrase_doc` 13/18 and `register` 10/18 for `bench-docs`, not 11/18 and 9/18.
- "Prof → Professor" is no longer a residual rejection; the filter accepts it.
- The fact-level job does not run "at three distance levels" in the app; `engines.py:170` forces `light` only. Three levels exist only in the CLI.
- The document-level job is described as if it had been exercised ("re-extract the original as a baseline"). The ledger shows no re-extraction calls; it has never run on real data, and its baseline is a cache hit, not a fresh extraction.
- The game builder's owners are not primarily "guessed": the extractor's `subject` field decides first (`game_builder.py:197-212`). Qiso's one-sided game came from role-card facts being categorised `context`/`constraint` (never actions) and shared-document commitments having the Mayor as subject.
- The brief's main suspicion about perturbation validity (false accepts on red lines or dropped content) is the smaller problem; the filter rejected all 12 adversarial probes. The dominant threats are on the recommendation side (sections 3.1–3.5).
- The 5% human-review sample "is written" but has never been judged; the Week 3 gate is open, not passed.
- Cost "about $1.50" for the Sim 2 rehearsal is not derivable from any file; the only hard number is $22.61 total October spend before this pilot.
- `README.md` says the app default is HUIT OpenAI `gpt-4.1-mini`; `.env` and the ledger show Bedrock Opus 5.5. Documentation drift, not a build issue.
- The Qiso "128 variants all stable" is reported in the brief as an observation about the builder; it is a consequence of unit selection (0 of 4 action facts reworded), which the brief did not identify.
