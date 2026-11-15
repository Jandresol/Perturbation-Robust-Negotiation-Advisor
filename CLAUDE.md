# CLAUDE.md — Perturbation (Rewording) Engine

Instructions for building the **perturbation engine** of Plan A. The source
of truth is `README.md` §3.2, §4, §6 and `PLAN_A_REWORDING.md` §1.2, §5. If
this file and those disagree, the plans win; flag the conflict and don't
quietly pick one. The general behavioural rules in `../CLAUDE.md` also apply.

## 1. What the engine is (and is not)

The engine takes a negotiation package `P` (or its atomic facts `F`) and
returns `K` **accepted rewordings** `P′_1..P′_K`: the same facts in
different words. By Assumption M, every accepted `P′` describes the same
true game, so **any downstream change in advice counts as error**. So the engine's
main job is to keep meaning fixed. Producing variety comes second.

**In scope:** the four operators, the acceptance filter, `d_emb`, the
random-noise control (B4), and logging.

**Out of scope:** anything that changes content. That means no inserting or
dropping facts, no reframing that fails entailment, and no counterfactual
shifts of any kind (BATNA, goal values, turns). Those belong to Plan B. If a task
seems to need one, stop and ask.

## 2. Operators (README §3.2)

| Operator | Unit | Changes |
|---|---|---|
| `paraphrase_fact` | one atomic fact | wording of that fact |
| `paraphrase_doc` | one source document | wording of the whole document |
| `reorder` | package | order of documents or facts (no LLM needed) |
| `register` | document | tone (formal ↔ plain), same content |

- Each LLM operator takes a requested **distance level**: `light`,
  `moderate` or `heavy`. That way `d_emb` covers a range for study S2.
- The engine runs at two entry points: whole package (before atomising) and
  fact level (between game-builder steps 1 and 3). Fact-level output must
  keep the `fact_id` so changes can be traced back to individual facts.

## 3. Acceptance filter (all three must pass)

1. Cosine similarity to the original ≥ `τ`, using one fixed open sentence
   encoder (MTEB-class).
2. **Bidirectional** NLI entailment (original ⇒ rewording and back).
3. **Hard facts unchanged**: numbers, names, dates, quantities, red lines.
   Check this deterministically. Extract the hard facts from both texts and
   compare them. Don't ask an LLM.

Log every rejection with its operator and the check that failed. Report
rejection rates per operator. Write a 5% random sample of accepted
rewordings to a file for human review (the Week 3 gate needs ≥ 95% of the
sample judged meaning-preserving).

## 4. Distance and the noise control

- `d_emb(P, P′)` = cosine distance, averaged over the units that changed.
  Store it on every accepted rewording.
- **Random-noise control (H2, baseline B4):** character- and word-level
  noise tuned to match a target `d_emb`. It is deliberately **not**
  filtered for meaning. Keep it in a separate code path, labelled as
  control output, so it can never mix into the accepted rewordings.

## 5. Where the code goes (README §11)

```
negotiator/reword/
  operators.py   # paraphrase_fact, paraphrase_doc, reorder, register
  filter.py      # cosine, bidirectional NLI, hard-fact freeze
  embed.py       # one encoder, loaded once; sentence splitter
  noise.py       # random-noise control (B4)
  engine.py      # runs operators + filter over units; keeps noise separate
negotiator/prompts/reword_*.md   # prompts as .md files, never inline strings
negotiator/llm.py                # the single seam for model calls
scripts/reword.py                # CLI: --facts runs/<id>/facts.json --k 16
tests/test_reword_*.py
```

[ASSUMPTION] The README's layout is rooted at `Final Build/`. In this repo,
code goes at the repo root.

## 6. Engineering rules for this engine

- **All model calls go through `negotiator/llm.py`.** Use the same
  prompt-hash cache pattern as `../pipeline/llm.py`. Every call must be
  cached and reproducible, because rewordings are re-run many times in
  S1–S5.
- **Seeds and config:** `K`, `τ`, the NLI threshold, the encoder name and
  the model all come from `configs/default.yaml`. Don't hard-code them.
  These are **frozen** before the live test (README §10), so make freezing
  easy.
- **Output records** (one per rewording): `id`, `source_id`/`fact_id`,
  `operator`, `level`, `text`, `d_emb`, `cos`, `nli_fwd`, `nli_bwd`,
  `hard_facts_ok`, `accepted`, `reject_reason`, `model`, `prompt_hash`,
  `seed`.
- **Same-text resampling (B2)** is not the engine's job. It reuses the
  original text with a new seed downstream. Don't fold it into the
  operators.
- Start with small `K` pilots. Cost is a known risk.

## 7. Tests that define "done" for the engine

- `reorder` is a permutation: the multiset of facts is identical.
- Hard-fact check: a rewording that changes one number or name is rejected.
- A known paraphrase passes; a known negation or contradiction fails NLI.
- Noise control output never reaches the accepted set.
- The cache works: a repeat run makes zero model calls.
- Running it on Simulation 2 facts gives `K` accepted rewordings per unit,
  with `d_emb` spread across the three distance levels.

## 8. API key setup

Claude is reached through **Harvard's AWS Bedrock gateway** (HUIT "AI
Services - AWS Bedrock" v2, docs at
portal.apis.huit.harvard.edu/docs/ais-bedrock-llm/1/overview), not the
Anthropic API directly:

- The Harvard portal key goes in **`.env`** (gitignored) as
  `ANTHROPIC_API_KEY=...`. It is sent as an `x-api-key` header.
- `llm.base_url` in `configs/default.yaml` is
  `https://apis.huit.harvard.edu/ais-bedrock-llm/v2`.
- `negotiator/llm.py` uses the SDK's `AnthropicBedrock` client. The gateway
  proxies Bedrock's `/model/{id}/invoke` path, which is what that client
  calls. Passing `api_key` stops the SDK from AWS-signing the request.
- Model IDs are Bedrock inference profiles: `us.anthropic.claude-opus-5-5`
  (the default) or the `global.` variant. List the available ones with
  `GET {base_url}/inference-profiles`.
- Billing is pay-as-you-go. `GET .../ais-bedrock-llm/apigee/quota` shows
  the remaining budget; a 429 means the budget cap was hit.
- Server-side refusal fallbacks are not available on Bedrock. A refusal
  raises an error rather than silently switching models.

Never print, log or commit the key.

## 9. Known limits of the current engine

- Filter cosine is the mean of sentence embeddings, so it barely moves for
  a dropped sentence in a long document. NLI (both directions) is what
  catches content loss. `tau` still needs calibrating on the human sample.
- NLI premise windows are runs of 1–3 sentences. A cross-encoder reads a
  sentence in the middle of a longer premise as "neutral".
- The hard-fact check covers digits, number words up to twenty (except
  "one", which is usually a pronoun), percentages and capitalised names.
  Line starts count as sentence starts, and "1." list markers are ignored.
- Red-line units (`red_line: true`) must also keep their force classes:
  prohibition, obligation, permission, exclusive ("only") and universal
  ("all"). On all units this rejected 19/155 accepted fact rewordings and
  36/138 document rewordings in past runs, mostly good paraphrases, so it
  applies to red lines only.
- Benchmark (2026-10-23; `runs/bench-docs`, `runs/bench-facts`, figures
  in `runs/bench-figures` via `scripts/plot_rewordings.py`):
  - Facts (9 sentences, k=3): 79/81 accepted.
  - Docs (3 Sim 1 docs, k=2): paraphrase_doc 13/18, register 10/18 (after
    the name-check fix; the review of 2026-10-27 recounted the run files).
  - Requested strength does raise `d_emb` monotonically.
  - Residual rejections:
    - NLI on sarcastic or exclamatory lines ("Wtf?!" → "What on earth?!").
    - Hard-fact false positives where PDF extraction runs a heading into
      the next sentence ("Quick Summary After …").
    - (Prof → Professor no longer rejected.)
  - The filter is deliberately strict; loosening it is an open decision.
    Cleaner extraction (atomiser) should remove the heading artefacts.
- With `reword.independent: true` (the default), each candidate is its own
  call with `seed + i`, so candidates are independent samples. With it off,
  one call returns all `k` and they are correlated.
- The `model` field records the model the API reports serving each call.
