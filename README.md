# Perturbation-Robust Negotiation Advisor

An AI-assisted tool that helps a human team prepare for and participate in a two-team, mixed-motive negotiation. LLMs interpret the scenario and develop options during preparation. During negotiation, a non-LLM planner updates recommendations from confirmed exchanges. Humans make every decision.

## Run the frontend

```sh
python3 server.py --port 8000
```

Open http://localhost:8000. Choose **Upload documents** to read a mixed batch of PDF and DOCX source documents, import a package JSON, or choose **Explore example workspace** to try preparation, strategy selection, confirmed negotiation events, and research inspection. The example is illustrative. The local Python server supplies the HUIT source-analysis API and persistent SQLite cache; PDF and DOCX text extraction runs in the browser. Preparation opens on a printable brief and critical sources, with no sentence-approval queue. Upload first using the optional shared/specific/role-card buckets. Analyze the files to infer editable roles and document summaries, tags, claims, and arguments. Connect the package-to-game and rewording services for baseline game inference and bounded planning; source corrections remain optional and targeted. Semantic model inference remains with the external engines. See [PIPELINE_INTERFACE.md](PIPELINE_INTERFACE.md) for the dataset contract, session handoff, and checks.

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

Source inference configuration: put the course key in `.env` as `HUIT_API_KEY` (the existing `ANTHROPIC_API_KEY` name is accepted for compatibility). See `.env.example` for model/provider settings. The default is HUIT OpenAI Direct v2 with `gpt-4.1-mini`; Bedrock Claude is also supported by configuration. Restart the Python server after changes. Analysis records live in ignored `.data/analysis.sqlite`, survive restarts, and are invalidated by text, scope, model, prompt/schema version changes. See [schemas/source-analysis.example.json](schemas/source-analysis.example.json) for the response shape.


For an end-to-end integration test before peer services are available, open **Pipeline settings → Use local reference engines**, then **Preparation brief → Build strategy options**. Newly uploaded packages default to these local engines. They make no network/model calls. The reference game models reciprocal confirmation of source interpretations using explicitly illustrative utilities; it is not a calibrated model of the real negotiation. Edit its labels, owners, weights and forbidden actions in Pipeline settings. The bounded wording engine targets K = 128 distinct rule-based wording substitutions and re-plans each resulting reference game; semantic entailment and ethics certification remain unimplemented. Formatting controls are unscored and excluded from stable/sensitive/changed totals. The original baseline is retained. External peer endpoints can replace either local engine.


The local wording generator now targets **128 distinct wording substitutions**, using bounded phrase rules and combinations, with numbers, known entity names, and listed modal/negation tokens checked. It no longer fills the target with formatting controls. Insufficient inputs produce an explicit shortfall. Existing saved controls remain distinguishable in Research until the run is regenerated. These candidates still require semantic entailment/audit; comparing them with a category-based reference game does not establish semantic robustness. No model calls are made by local generation.


## Integrated teammate engines

The app now calls both teammates’ engines through the same server. Branch revisions are recorded in `configs/engine-sources.json`; frontend changes are preserved.

```sh
python3 -m venv --system-site-packages .venv-engines
.venv-engines/bin/python -m pip install -r requirements-engines.txt
.venv-engines/bin/python server.py --port 8000
```

Wording tests start automatically once an interpreted package opens, with progress and Stop/Retry controls at the top of Research. In preparation, **Sources & strategy analysis** also offers **Test strategy against alternative readings**. New and legacy default workspaces use `peer:game` and `peer:perturbation`. Explicit external endpoints are preserved. Pipeline settings offers **Use teammates’ engines** and **Use local reference engines** as separate choices. Each interpreted fact set gets one automatic attempt. Saved attempts and failures do not automatically retry on reload; active negotiations do not start new automatic jobs.

- `game_builder.py` and `solver.py` build and solve source-linked commitment games without model calls. Utilities and ambiguous ownership are rule-based estimates, visibly labeled illustrative. Their outputs do not replace your source-grounded decision brief.
- `negotiator/reword` generates fact paraphrases and checks embedding similarity, bidirectional NLI, and names/numbers. Accepted readings are passed through the game builder and solver; the Research matrix shows actual comparisons. Source quotations and canonical facts are never rewritten. Controls and document-order permutations are not counted as paraphrases.
- The app uses its existing HUIT provider/model and `HUIT_API_KEY`, rather than the standalone benchmark’s Claude default. Requests reuse `.data/analysis.sqlite` gateway responses, including invalid/incomplete paid outputs. No automatic paid retries or top-up loops. A run selects at most 16 decision-ranked claims and requests at most 8 candidates each. Rejected or duplicate candidates create an explicit shortfall below 128.
- Similarity and NLI models load locally before paid generation. The first run may download them. Background jobs expose progress and support cancellation; an already active model request can finish and be cached, but cancellation prevents subsequent calls. A failed/cancelled rewording job leaves the baseline available. Semantic filter acceptance is not a human audit or robustness certificate; strategy-release gates remain false.

The same-origin API provides `GET /api/engines/config`, `POST /api/engines/jobs`, `GET /api/engines/jobs/{id}`, and `POST /api/engines/jobs/{id}/cancel`. Jobs accept the existing frozen-fact package contract. The standalone `game_service.py` and `scripts/reword.py` remain available for teammate workflows.

Research charts use saved measurements from the current case. An expandable examples section also contains the six original PNG/PDF figures and benchmark CSV for both `sim1` and `sim2` from the perturbation branch under `results/perturbation`. These saved benchmarks are labeled separately from current-case analysis; viewing them makes no model requests.


## Source-derived preparation brief

Preparation now starts with **Understand the case**, followed by the decision brief, package-specific negotiation issues, options/responses, and searchable sources. It works before a game or planner result exists. The heuristic game builder, planner, engine settings, live negotiation, and Research contracts are unchanged.

Tracing the original FWB role card exposed three losses: extraction versions differed in quantity coverage, the 64-claim synthesis cap dropped details, and fixed issue buckets displayed only the first matching position. Extraction now requests reasons, original quantities, force, attributed accounts and prior rejection. Synthesis reserves all role-card claims before selecting up to 128 ranked claims. Original role paragraphs are separately identified evidence passages; they are never promoted into canonical game facts. The context/issue schema cites these passages when a detail was absent from extracted claims. Refresh and intake require a nonempty issue synthesis (decision-synthesis-v3); an incomplete response leaves the saved workspace intact. Lossless text-wrapper schema drift is normalized from the saved paid response, without regeneration. Every cited passage remains accessible rather than keeping only one passage per document. Raw role passages also remain available in legacy saved workspaces.

Issues are generated from the package, with separate positions, reasons, conditions, prior alternatives/reception, dependencies, questions and arrangements. Original text and extraction details remain in Sources, outside the main brief. Numeric conditions omitted from an issue are retained when they come from the same original role paragraph as its cited claims. Shared source context is labeled as such, not treated as proof of a causal dependency. Inferences and unresolved interpretations are labeled; unsupported passage references are quarantined rather than guessed or automatically retried. Explicit advice still requires source support. Repeated extracted texts are grouped in source summaries and never described as independent corroboration.

Existing document and model responses remain cached. Updated schemas scope new extraction/synthesis artifacts; existing workspaces can choose **Refresh detailed brief** to generate the richer interpretation. The first refresh of an older schema can require new model calls. Subsequent identical requests reuse the new artifacts across renamed files and server restarts. Changing a file's role bucket can change the case interpretation.

Verification: `node --test tests/*.test.js` covers independent UI helpers and planning. `pytest tests/test_preparation_details.py tests/test_inference.py tests/test_streaming.py tests/test_peer_engines.py tests/test_game_builder.py` covers evidence binding, caching, incomplete/unverified output handling, API streaming and engine compatibility. The focused original-document FWB regression output is local in ignored `.data/fwb-detailed-regression-v3.json`; with that artifact present, run `NODE_PATH=/private/tmp/negotiation-browser/node_modules node tests/preparation-details.browser.cjs` for source passage navigation, preserved timing/staffing/access details, responsive layout, and zero model calls while browsing. Original private documents and regression outputs are not bundled into production assets.

Preparation has a persistent Brief / Sources reading switch. Source selection/search and each view’s scroll position survive switching. The main brief has four reading sections; options and prior reception are integrated into their issues, and each issue has one grouped evidence control. Strategy results and processing details live in Research. `tests/preparation-refresh.browser.cjs` verifies refresh/save/reload, edit preservation, navigation, evidence access and compact layout using a mocked response with no paid calls.

Research case figures now render locally with Matplotlib through `POST /api/engines/figures`, reproducing the benchmark chart layouts: grouped acceptance bars, operator panels for embedding distance and bidirectional NLI, stacked rejection bars, a log-log matched-noise plot, and a diverse original/reworded passage table. Recorded operator/strength groups determine the panels; missing controls or metrics are never filled with benchmark data. PNG/PDF and a measurements CSV are cached by content hash under ignored `.data/research-figures` and served through a restricted asset route. Rendering and downloading make no model calls. Legacy peer semantic records recover fact/light labels from their saved method/frame; new records include their NLI threshold.


## Workspace navigation and team decisions

Each workspace has persistent **Sources**, **Preparation**, and **Negotiation** tabs. Uploading from Sources adds documents to the existing package, reuses existing extraction caches during refresh, and preserves the plan and conversation. Initial setup retains the package uploader. Save/export, settings and advanced Research are workspace controls. Source citations open a right-hand drawer with attribution, surrounding text and full-document access without changing the active preparation step.

Preparation has three clickable destinations: **Understand the case**, **Work through the issues**, and **Review your plan**. Review completion is stored only after the user presses the review button; visiting or generating content does not mark a step reviewed. These are navigation controls, not gates. Issue notes and edited positions are stored separately from the generated source synthesis. Arrangements added to `preparation.teamPlan` are tentative choices, with source references and conditions; they never populate accepted commitments. The current team plan is copied into a session when the user starts or returns to negotiation.

The live workspace separates the current proposal, issue responses/next questions, and the conversation record. Manual proposals are recorded as nonbinding conversation notes. Confirmed exchanges update only the issue explicitly selected by the user; resolving an issue remains a team assessment. Human-confirmed agreements have their own terms, owners, conditions and confirmation timestamp, separate from modeled commitment IDs. Close/review records the final agreement or unresolved outcome and follow-up, and survives reload/export. Timers remain off until the user explicitly starts a timed rehearsal.

Run `node --test tests/workspace-flow.test.js` for the separation between tentative and accepted state. `tests/workspace-flow.browser.cjs` exercises the complete navigation/review/plan/proposal/agreement/outcome flow, citations, source addition and persistence with mocked source inference and no paid model calls. `tests/python-figures.browser.cjs` checks that advanced Research and downloads remain available through workspace controls.
