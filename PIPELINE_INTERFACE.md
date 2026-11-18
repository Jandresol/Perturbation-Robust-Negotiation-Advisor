# Preparation workflow and integration contract

The user workflow follows [Detailed_Plan.md](Detailed_Plan.md), especially §§5, 18.2, 20.1, and 20.3. Start the app with `python3 server.py --port 8000` and open http://localhost:8000.

## What the team does

Upload shared PDFs/DOCX files and our private role card, identify our side, then read the preparation brief. During team discussion, inspect the three critical sources, correct material errors, and choose an opening and fallback. Source inspection is optional; there is no sentence-by-sentence approval queue and no minimum number of reviewed facts required to run inference.

The main screen presents the objective and outside option, opening/fallback, red lines, available trade-offs, response branches, three high-impact assumptions, original source citations, and unresolved concerns. Technical traces remain in Pipeline settings or Research. The brief can be printed even when inference is incomplete; unavailable fields are explicit rather than invented. Team decisions can optionally override generated brief entries.

The source reader supports package-wide search, page navigation, shared/private classification, and saving passages as source notes. Local sentence rules provide an optional excerpt index, not canonical atomic facts or LLM inference. Old saved packages with pending excerpt suggestions load without creating review obligations. Accepted legacy edits are preserved.

## Automatic preparation

After a new document package is installed, the app starts preparation using configured connections. Connection URLs are stored locally across packages. Without a game-builder endpoint, the source draft is immediately available and the app states that inference is not connected. It does not redirect users to manual data labeling.

1. Send source documents and our role information to the package-to-game service. That service extracts source-linked facts once and returns a canonical game.
2. Run the bounded deterministic local planner on the baseline, when the game contract is supported.
3. Store the baseline separately before additional readings run.
4. Send the fixed canonical fact set to the rewording service during prep only.
5. Retain the baseline if additional work fails, is incomplete, or has no validated release gates.
6. Stop generation at five minutes and assemble available outputs with a deterministic brief template. The brief target is six minutes; team discussion runs through twelve minutes. Targets are displayed as targets, not runtime claims.

The active run records stage statuses and timestamps. Stop/cutoff aborts requests and active planning; late results cannot publish. Reload marks interrupted runs explicitly while retaining available artifacts. The local server implements API-backed source extraction and case synthesis. The game builder, advisors, rewording engine and semantic equivalence checks remain separate components.

## PDF and DOCX intake

PDF.js 6.4.299 is bundled locally in `vendor/pdfjs` with its Apache 2.0 license, worker, CMaps, and fonts. Original PDF binaries are not persisted. Filenames, extracted text, page numbers, and missing-text pages are retained locally and in exports.

Limits: 30 documents, 20 MB each, 100 MB total input, 500 pages per document, and 2 million extracted characters per package. Corrupt/password-protected/textless files report individual errors; successful files remain usable. Scanned pages need OCR upstream. Tables and multi-column reading order require source inspection when material.

## Package schema

`schemaVersion: 1`; `id` and `title` are stable nonempty strings. `parties` contains `us` and `opponent` labels. Optional strings: `role`, `objective`, `walkAway`. Every collection below is required and may be empty. IDs are unique within collections.

| Collection | Required item fields |
| --- | --- |
| `sources` | `id`, `title`, `text`; optional `pages: [{number,text}]`, `emptyPages`, `visibility: shared/private`, `format: pdf/docx`, `sections: [{number,text}]` |
| `facts` | `id`, `text`, `sourceId`, `quote`; optional `page`, attribution, modality, conditions, protected tokens |
| `actions` | `id`, `label`, `owner: us/opponent`, `factId` |
| `strategies` | `id`, `title`, `opening`, `fallback`, `actionIds` |
| `variants` | `id`, `factId`, `text`, `outcome: stable/sensitive/changed/unscored/rejected` |

Quotes must occur verbatim in their source. Fact/action references must resolve. Generated rewordings remain variants with parent fact mappings, never original source quotations. Optional strategy arrays: `redLines`, `assumptions`, `ethicsFlags`, `branches`. `meanScore` and `worstScore` are optional normalized model estimates in [0,1]. Omitted scores display as unavailable.

Optional `pipeline` is an ordered array of up to seven `{status,detail?}` objects: ingest, extract, build baseline, validate rewordings, plan/cross-score, advisor review, publish brief. Status is `pending`, `running`, `complete`, or `failed`. Missing work is not labeled as completed. UI state, source index, team edits, corrections, run records, and the preserved baseline live under `preparation`. **Export package** omits this UI state; **Save export** includes the complete workspace for restoration. JSON imports accept up to 25 MB.

## Service requests

Configure URLs in Pipeline settings. The app sends:

```json
{
  "schemaVersion": 1,
  "packageId": "stable-package-id",
  "task": "prepare",
  "factSetFrozen": false,
  "package": {
    "schemaVersion": 1,
    "id": "stable-package-id",
    "title": "Case title",
    "parties": {"us":"Our team","opponent":"Other team"},
    "sources": [], "facts": [], "actions": [], "strategies": [], "variants": []
  }
}
```

The real request includes all sources and available artifacts. The first request may have **zero facts**. The game builder performs extraction; it must not require manual fact approvals. The rewording request has `factSetFrozen: true` after the baseline is saved. It receives the original extracted facts as the control.

Private source text is included for our-side inference, so use endpoints authorized to process role information. No API credentials are stored by this frontend. Cross-origin services must allow the app origin and JSON POSTs through CORS.

### Game-builder response

```json
{
  "packageId":"stable-package-id",
  "facts":[
    {"id":"f1","sourceId":"source-1","page":1,"text":"An attributed atomic claim.","quote":"Exact text in source-1"}
  ],
  "actions":[
    {"id":"a1","owner":"us","label":"Provide a workshop","factId":"f1"}
  ],
  "game":{
    "maxOffers":3,
    "maxActionsPerSide":2,
    "goals":[
      {"id":"g1","type":"all","actionIds":["a1"],"usValue":-2,"opponentValue":4}
    ],
    "forbiddenActions":[],
    "assumptions":["An unresolved modeling assumption."],
    "opponentReadings":[{"id":"reading-1","values":{"g1":3}}]
  }
}
```

Quotes/references must match the actual uploaded sources. `strategies` may also be supplied if an external planner ran. Corrections preserve quotations, record before/after/reason/time, and mark existing model recommendations stale until rebuilt. Canonical facts are not silently replaced by rewording results.

### Rewording response

```json
{
  "packageId":"stable-package-id",
  "variants":[
    {"id":"v1","factId":"f1","text":"Generated alternative wording.","outcome":"unscored","validation":"Actual semantic filter evidence goes here."}
  ]
}
```

Results can be inspected without replacing the baseline. To publish a replacement strategy menu automatically, the response must additionally provide `release: {sourceSupport:true, feasibility:true, ethicsReviewed:true, freshRescored:true}` and a valid `strategies` array. These fields attest to upstream work; the browser does not perform or independently certify those checks. Absence of a gate preserves the baseline. Sample agreement is not numerical certification or a calibrated probability of human behavior.

The stratified human audit in Detailed_Plan §3.2 concerns accepted **rewordings**, including a pilot-defined minimum sample; it is not manual approval of every initial sentence. No blanket “5% of facts” gate is introduced.

## Local planner scope

`planner.js` runs in a worker and supports 1–12 actions, up to 64 linear/all-or-nothing goals, 1–4 of our offers, 1–2 new commitments per side per offer, and up to 16 additional opponent readings. Exact memoized search under an incremental-opponent-utility response rule generates candidate sequences; pooled sequences are evaluated on the same supplied models and sorted by worst and mean estimated value. Forbidden actions are excluded. Textual red lines must be represented in the supplied game.

This is a bounded baseline, not the complete alternating-proposer/belief-state solver in Detailed_Plan §§4 and 20.2. It does not claim calibrated beliefs, independent re-scoring, LLM strategic/ethics review, or numerical stability certification. The full planner and advisor/aggregation stages remain external work. The UI keeps these limitations explicit.

## Live negotiation and verification

Structured events still require operator confirmation before affecting state. Offers and notes are nonbinding; acceptance of an unresolved offer adds its complete action bundle. Binding commitments are monotone. This confirmation remains required as specified in §18.3, independently of optional prep source inspection.

`node --test tests/*.test.js` checks provenance, commitment transitions, planner behavior, legacy migration behavior, concise brief assembly, and cutoff rules. `tests/preparation.browser.cjs` covers zero-approval automatic inference, baseline preservation after failed rewording, saved decisions, and responsive views. `tests/pdf.browser.cjs` covers PDF extraction and malformed/textless input. Browser tests require Playwright, a server on port 8000, and Chrome (`CHROME_PATH` can override its location).

DOCX text extraction uses bundled Mammoth 1.13.0 in a worker and renders escaped plain text, including table text. Word documents have text sections rather than printed page numbers. The source index retains `section` references with `page: null`; engine facts may also supply `section`. Raw Word binaries are not retained. Extraction can be cancelled and times out after 30 seconds. Empty/corrupt Word files report individual errors without removing readable documents. Legacy `.doc` must first be saved as `.docx`. See [Mammoth API](https://github.com/mwilliamson/mammoth.js#api) for the extraction API. `tests/docx.browser.cjs` covers mixed formats, tables, provenance, persistence, and unreadable DOCX input.

## Upload-first source interpretation

The three optional batch uploads are shared information, side-specific information, and our role card. Side-specific and role-card buckets have private visibility. Roles/title/objective are editable inputs below the uploads, initially empty; the model fills supported values after **Analyze package**. Unresolved roles stay unknown rather than silently choosing the first two actors. Users can continue with sources when inference is unavailable. No individual file categorization or sentence approvals are required.

`POST /api/sources/parse` accepts `{package:{id,sources}}`. A document call returns summary, tags, type, entities, represented-side hint, atomic claims and attributed arguments in one output. Quotes are checked against original text before caching; factual assertions retain modality, attribution and conditions. Argument premise indices are checked and mapped to stable fact IDs. A separate case call uses compact document analyses and canonical claims (not original full texts or repeated quotations), plus upload buckets, to infer the case and our side. See `schemas/source-analysis.example.json`. The returned `facts` is the flattened canonical claim set; unknown objectives and outside options remain null. Extracted red lines are inferred interpretations until confirmed/encoded in the game; they are not silently made hard constraints.

`backend/inference.py` uses the documented HUIT OpenAI v2 or Bedrock invoke endpoints. The key is read from server environment/`.env`; never returned to the browser. `.env`, `.data` and Python/backend source are not served as static assets. Run `python3 server.py`, rather than a plain static server. HUIT/OpenAI is the tested default route; the Bedrock route is implemented but requires separately enabled access and an appropriate model ID.

SQLite stores successful document/case artifacts and provider token-usage records in `.data/analysis.sqlite`. Cache keys include project scope, extraction/prompt/schema version, provider, model and relevant semantic input. Document keys exclude filename, binding ID, bucket and our side; case keys include buckets and canonical analyses. Repeated or renamed files reuse document outputs, with citations remapped to the current binding. Changing buckets refreshes the case without re-extracting the document. In-process locking prevents simultaneous identical cache misses. Failed, incomplete, or unverifiable outputs are retained privately as paid responses for local revalidation; they are never published as validated artifacts. Completed documents survive a later case failure. The cache is project-local; use separate CACHE_SCOPE values for separate access domains.

Limits include 100,000 extracted characters per document (oversized inputs are rejected explicitly rather than truncated), 4,500 output tokens per call, a 75-second provider request timeout, and a 210-second document-processing budget before case synthesis. Completed analyses are retained if the budget is exceeded, so retrying resumes using cache hits. There are no automatic paid retries. This cache is for production intake only; experimental same-text resampling must use a separate explicit replicate policy rather than reusing these artifacts.

Check source parsing/cache behavior with `python3 -m unittest discover -s tests -p 'test_*.py'`. `tests/intake.browser.cjs` covers the upload-first dialog and a mocked API response. A successful real HUIT synthetic extraction is separate evidence from the mocked UI checks.

### Detailed-plan flow and remaining integration

The user flow follows Detailed_Plan.md §§18–20: upload categorized documents → explicit API inference → editable case/constraints → baseline game and local plan → bounded preparation rewordings → brief and team decisions → confirmed live exchanges → debrief/export. The main brief includes alternatives and unresolved concerns; research matrices stay in Research. Current generation cutoff is measured from starting the game preparation run, so upload/API intake time must also be counted when evaluating the complete 12-minute preparation target.

Live events include offers, acceptance, rejection, questions, tentative agreements, notes, and new/unmodeled issues. Only confirmed acceptance of a complete unresolved offer adds commitments. Tentative agreement does not resolve an offer. Unmodeled issues remain in the log and display a coverage warning; free text never silently rebuilds the game or revises red lines.

Remaining plan requirements are not presented as implemented: opponent-belief updates, live re-planning/next-move cards, deterministic shorthand entry, correction/undo of logging errors, and complete numeric enforcement of source constraints by the peer game builder. The local solver remains the bounded solver documented above. Confirmed textual red lines require explicit game encoding. A complete end-to-end timed rehearsal still depends on the peer engines.


### Paid-output retention and failed analysis

Automatic model retries are disabled. Each completed gateway response is saved in the private local SQLite cache before JSON parsing, and each decoded model output is saved before source validation. Validation failures are not published as validated artifacts. Repeating an identical request rechecks saved output locally and does not purchase another response, including after a server restart. Partial documents remain available across a later case failure. Failed outputs created before this retention change cannot be recovered retroactively. Model/provider/scope or prompt changes identify a new request and can incur a new charge.

The call ledger records received gateway responses, including outputs that fail downstream validation. HUIT quota remains authoritative for money spent; a timeout or transport failure may have reached the provider without returning a savable response. A saved invalid response requires a local validator fix or an explicitly chosen new analysis, rather than a hidden paid retry.

### Source-only test runs

After upload/inference, Preparation → Test run → Start source-only rehearsal starts a 15-minute session without a game-builder connection. The team can set its own opening/fallback, read the current brief and evidence, confirm questions/tentative agreements/new issues/notes, and export or debrief. No API calls are made by the rehearsal. These observations do not encode binding commitments or refresh scores. Modeled offers/acceptances remain available only in the game-based workflow; the shared event model enforces this separation even on imported sessions.


### Built-in reference engines

`builtin:game` and `builtin:perturbation` dispatch in the browser via local-engines.js, with no HTTP or model calls. They use the existing peer result shapes and bounded local planner. New packages default to them; existing packages can enable them in Pipeline settings without replacing saved external connections automatically.

The reference game selects at most three source topics, creates reciprocal confirmation actions, and assigns explicitly illustrative process costs/benefits. It never claims to infer real concessions or human utility. Team edits persist in `referenceGameEdits`, and forbidden actions feed the planner. Imported/active session actions cannot be edited. Confirmed red-line evidence can exclude topics, but this does not implement full natural-language constraint reasoning. Global simulation notices and strategy assumptions expose these limits.

The wording engine targets K = 128 distinct candidates using bounded substitutions and combinations, checks numbers and listed modal/negation tokens, rebuilds the reference game, and compares canonical game fields and planner sequences. Because this builder uses fixed claim categories and identifiers, stability is expected and is not evidence of semantic-inference robustness. Legacy saved formatting controls remain unscored for robustness; new runs do not generate fillers. No entailment certificate or release gate is granted. Perturbation is preparation-only and cannot replace the baseline under the current release policy.


### Source progress and argument validation

`POST /api/sources/parse` accepts `Accept: application/x-ndjson` for a single streamed request. Events report each source entering processing, completing (including cached-output reuse, claim count and limitation count), or failing; case synthesis has separate milestones, followed by one result or error event. JSON responses remain available to existing clients. Per-source progress is indeterminate while waiting for the provider; completion counts reflect actual completed documents, not a fabricated token percentage. Completed paid requests continue caching if the client disconnects.

Arguments with out-of-range, noninteger, or excluded supporting claim indices are omitted with an explicit extraction limitation. References are never guessed or shifted. Valid claims remain available, and prior failed paid outputs can be locally revalidated under this rule without a new document model call. Uncached remaining sources or case synthesis still use the API normally.


### Source-linked advisory brief before game inference

Case synthesis now returns `caseAnalysis.brief`: opening, fallback, two alternatives, up to three response branches and critical assumptions, three selected evidence IDs, our constraints, opponent demands, decision authority, and potential trades. Advice items carry `{text, claim_ids, status}`; proposed advice is inferred, explicit evidence is supported, and unknowns remain explicit. Nonunknown advice requires valid selected evidence IDs. Only `our_constraints` populates new red-line suggestions, never opponent demands.

The existing case call is upgraded rather than followed by a second summarization call. Its input uses at most 64 ranked claims, original quote excerpts, compact arguments, short summaries and role metadata. At least one claim per document is retained; role-card/private commitments, constraints, authority and timing are prioritized. Selection coverage is exposed, and original source text remains accessible. Per-document extraction schema/version is unchanged, preserving all cached document analyses. The new case schema/input creates a fresh synthesis cache entry on first use.

Existing workspaces use **Generate preparation brief**. Explicit team role/objective/outside-option decisions, corrected claims and red-line decisions scope that cache. Editing those fields marks the advisory brief stale but does not automatically call the API. Manual opening/fallback overrides remain authoritative. Repeated unchanged inputs reuse synthesis, and invalid paid outputs remain retained under the no-retry policy. One uncached case synthesis is a paid call; this does not promise free regeneration after substantive input changes.

The brief renderer prioritizes an actual chosen plan, then source-based advisory synthesis. Reference simulation plans do not displace advisory openings. It ranks evidence instead of taking the first three facts. The main brief shows at most five priority concerns; routine per-document limitations remain under optional extraction details. The page, print brief and source-only rehearsal can work without a game, calibrated utilities or perturbation results.


### Voice capture and operator flow

The live exchange form begins with browser microphone recording, followed by editable text, speaker/event classification, then explicit review/confirmation. It defaults to a nonbinding note. Offer actions and acceptance/rejection references are shown only for the corresponding event types. No speech transcript automatically creates or accepts an offer, assigns a speaker, or rebuilds the game.

Audio uses MediaRecorder and is retained in browser IndexedDB (`negotiation-audio-v1`), independently of the API/SQLite analysis cache. Clips have persistent IDs, package IDs and downloadable blobs. Session JSON includes `event.capture` metadata (`method`, `audioId`, `rawTranscript`, `transcriptionProvider`) but not the audio binary; recordings must be downloaded separately. Playback persists across reload on the same browser/origin. Clips are bounded to two minutes per exchange; stopping or navigating away releases microphone tracks. Closing a tab during an unfinished recording can lose that unfinished clip.

Live transcription uses SpeechRecognition only when the operator explicitly enables it. Browser support varies, and the browser's speech service may process audio externally; it is not represented as on-device/private transcription. There are no HUIT calls for capture or transcription. Unsupported speech recognition falls back to recorded audio plus typed notes; unavailable/denied microphone access falls back to typing. Recording starts only on a user gesture. The operator must stop recording and review corrected text before logging an event. The raw transcript is retained separately from the edited event text.

Cached case inference now hydrates missing package/edit-form fields locally without a new API call, while preserving explicit team context edits. A current-step banner guides source interpretation, brief generation and team review before a live session.

### Comparison completion versus robustness outcomes

Research displays comparison completion separately from stable/sensitive/changed wording outcomes. Legacy local formatting controls retain `outcome: unscored` for robustness accounting, but carry `comparisonCompleted: true`, canonical game/plan comparison fields, and distinct Control unchanged/changed labels. Existing saved controls with both comparison booleans are recognized without rerunning them. The controls filter is separate from unfinished unscored readings. K remains the total run count, not a claim that all runs are validated semantic paraphrases.

Evidence ledger display labels use F1, F2, … plus a readable claim category. Source IDs and canonical fact IDs remain unchanged in data and exports; technical fact IDs are available under an expanded technical-reference disclosure. Source links navigate to the original document reader.


The local wording generator now targets **128 distinct wording substitutions**, using bounded phrase rules and combinations, with numbers, known entity names, and listed modal/negation tokens checked. It no longer fills the target with formatting controls. Insufficient inputs produce an explicit shortfall. Existing saved controls remain distinguishable in Research until the run is regenerated. These candidates still require semantic entailment/audit; comparing them with a category-based reference game does not establish semantic robustness. No model calls are made by local generation.
