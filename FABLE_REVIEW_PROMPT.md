# Review brief: Perturbation-Robust Negotiation Advisor

You are reviewing a COMPSCI 2822R final project at Harvard. The owner is Vedant Sandhu. You're working in
`/Users/vedantsandhu/Desktop/Fall2026/COMPSCI2822R/Perturbation-Robust-Negotiation-Advisor`.

Your job is an independent, evidence-based review of everything built so far, measured against the
project plan. One question matters most:

> **Can the current build show whether meaning-preserving perturbations (rewordings) of a negotiation
> package change the strategies and recommendations the system gives? If not, what's missing, and what's
> the shortest credible path to an answer?**

Treat everything below, including the build log, as claims to check against the code, the data and the
git history. Where your findings disagree with this brief, say so plainly.

---

## 1. The project in brief

The tool supports a human team in a two-team, turn-based, non-zero-sum (mixed-motive) negotiation set in
a humanitarian crisis. Both teams get a shared document package. Each team also gets its own private role
card.

The planned pipeline has three layers:
1. A model turns the package into a **commitment game** in the style of Benac et al. (2026,
   arXiv 2603.14066):
   - actions each side can commit to;
   - goals those actions satisfy (proportional or all-or-nothing);
   - a goal-utility matrix `G`, with our column taken from our role card and the opponent's column
     estimated as a spread of values.
2. A **non-model planner** solves the game.
3. **Model advisors** (strategic and ethics) review the plan and write a one-page brief.

**The research.** The perturbation studied is **rewording only**: the same facts in different words.
Meaning, attribution, modality, numbers, names, dates, conditions and red lines must all be preserved.
Under that assumption ("Assumption M"), every accepted rewording describes the same true game. So any
change in the advice signals sensitivity to wording. That isn't automatically an error, because ties and
equally good alternatives exist.

- **Primary question.** Does combining K reworded readings reduce decision-quality loss compared with K
  readings of identical text, at equal compute?
- **Supporting questions.**
  - How much do strategies change under valid rewordings?
  - At which pipeline stage does the change enter?
  - Does it track embedding distance?
  - Does a menu pooled across rewordings beat the controls?
- **Hypotheses H1–H6.** These include H1 (brittleness exists) and H3 (changes enter mainly through
  opponent-utility estimates near acceptance thresholds).
- **Required controls.**
  - **B2:** same-text resampling × K. This is the main control.
  - **B4:** random noise at matched embedding distance.
  - **B9:** direct sampling of opponent utilities. This is the hardest control.

**Sources of truth, in priority order:**
- `Detailed_Plan.md`. This is the full plan; read all of it.
- `PLAN_A_REWORDING.md`
- `README.md`
- `CLAUDE.md`: rules for the rewording engine.
- `../CLAUDE.md`: general behavioural rules.
- `EXECUTION.md`
- `PIPELINE_INTERFACE.md`

If you can, fetch the Benac et al. paper as well. Its document-to-game pipeline works **interests first**:
it extracts the outcomes each party wants, merges them into goals, scores each party's stance per goal
(which gives `G`), extracts actions, and maps actions to goals.

The timeline is 8 weeks from 2026-10-20 (`Detailed_Plan.md` §12). Today is about Week 2. The plan's
minimum build is in §20.3.

---

## 2. What has been built: claims to verify

### Branches (local only; nothing has been pushed recently)
- `main`
- `scaffold/frontend-architecture`: the teammates' frontend and engines. It is the upstream of the
  feature branches, so **do not `git pull`** on them.
- `setup/perturbation-engine-scaffold`: has a stash (`stash@{0}`) holding the owner's earlier
  model-based game builder and planner, with atomise, structure and elicit prompts. This is prior art for
  a model-based builder. `runs/game-sim2/` holds its output.
- `feature/doc-level-rewording`: commit `531c8d0`. Used for the live classroom run.
- `feature/live-advice-model`: checked out now. Has uncommitted work (see below).

### Commit history (`git log`)
1. `6a9f6e6` → `76aaf53`: frontend scaffold, document-driven preparation, decision brief, live
   negotiation UI.
2. `c2b0302`: integrates the teammates' engines.
   - `game_builder.py` is a rule-based builder with no model calls.
   - `solver.py` and `planner.js` do exact bounded offer search.
   - `negotiator/reword/` is the fact-rewording engine.
   - Jobs are served through `server.py` and `backend/engines.py`.
3. `531c8d0`: four groups of changes.
   - **Document-level rewording job.** The `perturbation-doc` job kind does "reword before
     extraction":
     - re-extract the original as a baseline;
     - reword whole source documents;
     - filter them;
     - re-extract;
     - match the new facts to the old ones (`align_facts`);
     - rebuild the game and compare game and plan.
   - **Game builder fixes.** Role-card priority, matching by subject owner, initials as aliases, and
     skipping concerns, approval needs, joint-agreement facts and third-party facts.
   - **NLI fix.** Normalises ellipsis characters.
   - **Gateway hardening.** Low effort, 180 s timeout, at most 3 long calls at once, one retry, per-key
     locks, concurrent extraction.

### Uncommitted work in the working tree
- `backend/inference.py`: the case-synthesis output cap is raised to 20k tokens.
- **Per-exchange live advice from the model** (this branch):
  - a `POST /api/live/advice` route;
  - `AnalysisService.live_advice()` and the advice output schema;
  - the browser call in `live-strategy.js`;
  - rendering in `negotiation-ui.js`;
  - tests.

  This **deliberately departs** from the plan, which says "no LLM required for live action selection".
- `data/`: course packs and a session export. Untracked. Don't commit it.

### How each perturbation path works (check in code)
- **Fact level** (`negotiator/reword/`, `scripts/reword.py`, and the `perturbation` job in
  `backend/engines.py`):
  - The operators are `paraphrase_fact`, `paraphrase_doc`, `register` and `reorder`, at three distance
    levels.
  - The acceptance filter has three checks: cosine ≥ τ = 0.85 with `BAAI/bge-base-en-v1.5`; NLI in both
    directions with `cross-encoder/nli-deberta-v3-base` at threshold 0.5; and a deterministic check that
    hard facts are unchanged.
  - The embedding distance `d_emb` is stored on each rewording.
  - The noise control is in `noise.py`.
  - The CLI writes a 5% human-review sample.
- **Comparison.** Each accepted reading goes back through `game_builder.py` and `solver.py`. The outcome is
  labelled:
  - **stable**: game and plan unchanged;
  - **sensitive**: plan unchanged but game changed;
  - **changed**: plan changed.

  It does this through `game_signature` and `plan_signature` in `backend/engines.py`.
- **What the user actually sees** as recommendations is mostly the **model-written case synthesis and
  brief** from `AnalysisService.parse` in `backend/inference.py`: opening, fallback, issues, response
  branches and trade-offs. Check whether that brief is ever perturbed or compared across readings. As far
  as we know, it isn't.

### Observed runs and evidence (look in `runs/`, `results/perturbation/`, `.data/analysis.sqlite`)
- **Benchmark from 2026-10-23** (recorded in `CLAUDE.md` §9):
  - facts, k=3: 79 of 81 accepted;
  - documents: `paraphrase_doc` 11 of 18, `register` 9 of 18;
  - requested strength raises `d_emb` steadily.
  - Figures are in `runs/bench-figures`.
- **Sim 2 rehearsals through the UI.**
  - About 17 document extractions plus case synthesis took roughly 3.5 minutes and cost about $1.50.
  - The rule-based game builder produced **"No improving offer → Walk away"**. The opponent's possible
    moves existed only as demands.
- **Live classroom simulation, 2026-10-26.** The case was Border Authority Officer vs. Mayor of Qiso.
  - The pack is in `data/packs/` and the session export is `data/negotiation-workspace.json`.
  - The builder made 4 actions, all owned by the Mayor (the Officer's directives), so the only strategy
    was "Walk away".
  - The session ran in brief-led mode, so it recorded no commitments.
  - All 9 exchanges were logged as notes, and the rule-based live advice repeated one template.
  - A model-based live advice prototype was then built (see above).

### Known or suspected gaps (from a previous review; challenge these, don't adopt them)
- **The game builder is a placeholder.** Its utilities are fixed constants (−1, +2, and +3 for pairs
  matched by list order). Actions are fact sentences with guessed owners. The plan instead calls for a
  model-built game covering §5 steps 2–8.
  - **Consequence:** today's "changed" outcomes may measure how sensitive the regex and ownership rules
    are to wording, not how sensitive model-estimated games are to wording. That would make H3, Props.
    A2–A4, study S3 and control B9 untestable in the current build.
- **The planner** only searches offers from our side. Missing:
  - counter-offers (the proposer doesn't alternate);
  - a no-deal value;
  - acceptance margins (Prop. A4);
  - a trade-off table;
  - forward-looking acceptance. It uses the Benac "myopic reward" rule.
- **Missing entirely:**
  - the aggregator (averaged game, pooling, cross-scoring, fresh re-scoring);
  - contingent trees;
  - the quality-diversity archive and Vendi diversity score;
  - the ethics and strategic advisors acting on planner output;
  - opponent belief updates during the live negotiation;
  - the Benac game generator and game-to-text renderer, needed for scored games with a known true `G`;
  - same-text resampling (B2) and opponent-utility sampling (B9);
  - studies S1, S3, S4 and S5;
  - regret and other metrics;
  - a completed human audit of rewordings.

---

## 3. What to review

Work through these in order. Cite `file:line`, commit hashes and run folders as evidence.

1. **Plan-to-build alignment.** Map every component in `Detailed_Plan.md` to its implementation status:
   done, partial, placeholder, missing or deviates. That covers §5 steps 0–8, §7's components, §9's
   studies, baselines and metrics, §18's live loop, and §20.3's priorities. Mark each deviation as
   either justified or harmful to the research question.
2. **Validity of the main measurement.** Can the current outcomes (stable, sensitive, changed) answer
   "do meaning-preserving perturbations alter recommendations"? Look at:
   - **Perturbation validity.** The filter's false accepts and false rejects; whether the audit was done;
     whether the hard-fact check covers red lines; whether document-level rewordings can drop content
     that NLI misses.
   - **Recommendation source.** Which recommendation is compared: the solver plan, the model brief, or
     the live advice? Is the comparison the one a user would care about?
   - **The model in the loop.** Does the compared recommendation depend on model inference at all once
     facts are fixed?
   - **Outcome definitions.** Are plan signatures sensitive to ties, action-ID renumbering or ordering
     artefacts? Are "equally good alternatives" separated from real changes, as the plan requires?
   - **Confounds.** Extraction randomness versus wording effects. This is why B2 exists. Check whether a
     same-text control exists for the document-level path.
   - **Caching.** Do the prompt-hash caches make "repeat runs" trivially identical, and would that hide
     sampling variance?
3. **Evidence quality.** What do the existing runs actually show? Recompute key numbers from the files in
   `runs/` and `results/` where you can. Separate measured results from anecdotes.
4. **Engineering correctness on the measurement path.**
   - Read `negotiator/reword/*`, `backend/engines.py`, `backend/inference.py`, `game_builder.py` and
     `solver.py`.
   - Run the tests:
     - `.venv/bin/python -m pytest -q tests`
     - `node --test tests/*.test.js`
   - Report bugs that would bias the perturbation results. Skip cosmetic issues.
5. **The shortest credible path to the main result.** Propose a minimal experiment that can answer the
   main question by the end of the 8 weeks. Cover:
   - which recommendation to measure;
   - perturbation sets and controls (at least B2 alongside rewording × K);
   - packs and generated games;
   - metrics and statistics;
   - the call and token budget.

   Then turn it into prioritised tasks with exit checks, following the plan's own priority levels.
   Point out which tasks need the teammates, who own `game_builder.py`, `solver.py` and the frontend.

---

## 4. Optional pilot (real model calls, using Fable 5.1)

If it helps the review, run a **small** empirical pilot of the main question on Sim 2 (`data/packs/sim2`)
or the Qiso pack. Example design:
- Take the model-written brief from case synthesis as the recommendation.
- Generate it on:
  - the original text, n = 3 runs with different seeds or cache scopes. This is the same-text control,
    B2.
  - 3–5 accepted rewordings, from `runs/sim2-facts`, `runs/sim2-docs` or a fresh small run.
- Compare opening, fallback, red lines and issue list with a structured diff. A judge model is optional
  and must not be the same call that produced the brief.
- Report variation within same-text runs against variation within reworded runs.

Rules for the pilot:
- Estimate token use and cost **before** spending.
- Check the remaining budget first with `GET https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota`.
- Keep the pilot under **40 model calls** unless the owner approves more.
- Write outputs to a new folder, `runs/fable-review-<date>/`.
- Record the model ID, prompt hashes, token counts and seeds.
- A 429 response means the budget cap was hit. Stop and report.

---

## 5. Running models: the API key and model ID

- **Where the key is:** the file `.env` in the repo root. It's gitignored. The variable is
  **`ANTHROPIC_API_KEY`**. It's a Harvard HUIT portal key, not a direct Anthropic key.
- **Gateway:** Harvard's AWS Bedrock gateway at `https://apis.huit.harvard.edu/ais-bedrock-llm/v2`. The
  key goes in an `x-api-key` header. Calls use Bedrock's `/model/{id}/invoke` path.
- **Model:** use **`us.anthropic.claude-fable-5-1`** (confirmed in the gateway's inference profile list).
  `global.anthropic.claude-fable-5-1` also exists. The project default is
  `us.anthropic.claude-opus-5-5`.
- **App pipeline** (`server.py`, `backend/inference.py`, engine jobs):
  - The model comes from the `HUIT_MODEL` environment variable.
  - `load_env` only fills variables that aren't already set, so override per command **without editing
    `.env`**. Use a separate port and cache scope:

    ```sh
    HUIT_MODEL=us.anthropic.claude-fable-5-1 CACHE_SCOPE=fable-review .venv/bin/python server.py --port 8001
    ```

  - Requests and responses are cached in `.data/analysis.sqlite`. The model ID and `CACHE_SCOPE` are part
    of the cache key.
- **Rewording CLI** (`scripts/reword.py`, `negotiator/llm.py`):
  - The model comes from `llm.model` in `configs/default.yaml`.
  - Copy that file, for example to `configs/fable-review.yaml`, change `llm.model`, and pass
    `--config configs/fable-review.yaml`. Don't edit the frozen default.
  - The CLI uses the `AnthropicBedrock` SDK client with `ANTHROPIC_API_KEY` and caches by prompt hash.
- **Direct calls:** load `.env` in-process, for example with `backend.inference.load_env('.env')`, and
  send a Bedrock `invoke` body like the one in `AnalysisService._request` (`anthropic_version`,
  `max_tokens`, `system`, `output_config.effort`, `messages`).
  - Thinking tokens count against `max_tokens`.
  - Keep effort at `low` or `medium`, and leave enough `max_tokens` for JSON outputs.
- **Never print, log, echo or commit the key**, or any part of it. Don't `cat .env`. If you need to
  confirm the variables exist, print names only with the values redacted.

---

## 6. Constraints

- **Read-only by default.** If you need code, create a new branch from the current one, for example
  `review/fable-<topic>`.
- Don't commit unless the owner asks. Never push. Don't add a Claude co-author line or mention API keys
  in commit messages.
- Don't modify `configs/default.yaml`, the teammates' `game_builder.py` and `solver.py` (beyond
  proposals), or anything in `data/`.
- Course packs and role cards are private course material. Don't send them anywhere except the Harvard
  gateway.
- Follow `CLAUDE.md` and `../CLAUDE.md`. In particular: no counterfactual or fact-changing perturbations
  (that's Plan B), and flag conflicts between documents rather than silently picking one.

---

## 7. Deliverable

A report in Markdown, saved as `runs/fable-review-<date>/REVIEW.md`, with these sections:

1. **Verdict** (5–8 sentences). Can the current build answer the main question? Why or why not?
2. **Plan-vs-build table.** Each component, its status, evidence, and impact on the research question.
3. **Threats to validity.** Ranked, each with evidence and a concrete fix.
4. **What existing evidence shows.** Recomputed numbers and their limits.
5. **Bugs that bias results.** Correctness only.
6. **Minimal experiment design** for the main question, including controls, metrics, statistics and
   budget.
7. **Prioritised task list.** Exit checks, an owner for each (Vedant or a teammate), and the plan week it
   maps to.
8. **Pilot results**, if you ran one. Include cost.
9. **Where this brief was wrong.** List the places your findings contradict this brief.

Be direct and specific. Don't count prose differences as strategy changes. Keep the error, the sensitivity
signal and the equally good alternative separate, as the plan does.
