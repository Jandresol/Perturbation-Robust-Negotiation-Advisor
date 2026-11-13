# Frontend + User Interaction Scaffold

## Purpose

This document is the front-end scaffold for the Perturbation-Robust Negotiation Advisor. It defines the user-facing architecture, the simulation flow, and the interaction model for a Monday class demo where negotiation preparation happens before live discussion.

This is intentionally a scaffold only. The rewording engine, model logic, and final recommendation output are owned by other teammates. This front end is responsible for:

- presenting the negotiation package,
- allowing users to review assumptions and strategy options,
- simulating a live turn-based negotiation,
- recording decisions and outcomes,
- surfacing prep-stage perturbation insights without requiring live engine generation.

---

## Source-document structure the project is designed around

The actual negotiation corpus is a document bundle rather than a single file. The frontend and ingestion layer should assume a packet of heterogeneous source materials, such as:

- news articles,
- public posts and X posts,
- reports from humanitarian organizations,
- meeting minutes,
- official statements,
- local community and stakeholder interviews,
- PDFs containing direct quotes and factual claims.

A representative shape is:

```text
Negotiation_Source_Documents/
  01_News_Article_on_Gamma_US_Source.pdf
  02_News_Article_on_Gamma_German_Source.pdf
  03_News_Article_on_Beta_Swiss_Source.pdf
  04_Podcast_on_Beta_US_Influencer.pdf
  05_X_Post_from_a_Citizen_of_Beta_City.pdf
  06_X_Post_from_a_Citizen_of_Beta_Town.pdf
  07_X_Post_from_the_Child_of_the_Head_Surgeon.pdf
  08_Public_Post_on_HfA_Website.pdf
  09_X_Post_from_Beta_Town_Local.pdf
  10_WHO_Regional_Office_Report.pdf
  11_Meeting_with_the_Minister_of_Health_of_Beta.pdf
  12_Statement_from_the_UN_Humanitarian_Coordinator.pdf
  13_Meeting_with_Food_Without_Borders_Country_Director.pdf
  14_Minutes_German_Ambassador.pdf
  15_Minutes_Swiss_Ambassador.pdf
  16_Meeting_with_Child_Protection_International.pdf
  17_Local_Press_Summary.pdf
  18_Meeting_with_Local_Head_of_Police.pdf
  19_Meeting_with_District_Administration_Head.pdf
  20_Meeting_with_Patient_Association_Representatives.pdf
  21_Meeting_with_HfA_Head_Surgeon.pdf
  22_Meeting_with_Local_Hospital_Staff.pdf
  23_Meeting_with_Local_Guards_and_Families.pdf
  24_Meeting_with_Tribespeople.pdf
  25_First_Meeting_with_Tribal_Leaders.pdf
  26_Message_Between_Tribespeople.pdf
```

### Implications for the scaffold

The app should treat these documents as a shared evidence package, not as a single flat transcript. The interface should support:

- source list with source type and emitting party,
- fact extraction from each source,
- source attribution on every claim,
- filtering by document category, actor, or issue,
- grouping claims into topics such as logistics, safety, access, humanitarian conditions, and political constraints.

This is important because the negotiation engine will later use these documents as the basis for fact extraction, rewording, and robust strategy generation.

---

## 1. Product Goal

The scaffold supports a human team preparing for a negotiation by:

1. Loading a common negotiation package and private role information.
2. Showing the relevant facts, constraints, and goals in a structured format.
3. Presenting a small set of pre-generated strategy options from the planning engine.
4. Allowing a user to simulate back-and-forth negotiation turns.
5. Tracking commitments, concessions, and walk-away thresholds.
6. Showing how different rewordings or pre-planned perturbations influence the interpretation of the same situation.

The key idea is: the perturbation is pre-planned and pre-evaluated, not generated live during the negotiation itself.

---

## 2. System Architecture Overview

### 2.1 High-level layers

- Presentation layer: browser UI / dashboard / simulation canvas
- State layer: app state, negotiation timeline, turn log, selected strategy
- Integration layer: API calls to the planning engine, model outputs, and scenario data
- Domain layer: commitment game, negotiation facts, utility estimates, red-line constraints

### 2.2 Component boundaries

- Frontend app shell
- Scenario loader
- Fact board
- Role card panel
- Strategy menu
- Negotiation simulator
- Event log / transcript
- Decision summary / brief
- Settings panel for perturbation comparison

The app is designed so the engine can provide structured JSON, and the frontend only renders and manages human decisions.

---

## 3. Core User Experience

### 3.1 Monday-class interaction flow

For classroom use, the workflow should be simple and legible:

1. User selects or loads a negotiation scenario.
2. System shows the shared package and the user’s role card.
3. User reviews the extracted facts and key constraints.
4. System presents a brief set of strategic options:
   - opening offer,
   - fallback package,
   - walk-away threshold,
   - red lines,
   - likely opponent response scenarios.
5. User chooses a strategy card and enters the first proposal.
6. The simulation tracks one turn at a time.
7. User selects acceptance, rejection, or counteroffer.
8. System updates the commitment state and highlights the next best move.
9. A final summary displays the negotiated outcome, concessions made, and risk flags.

This keeps the negotiation flow understandable in a classroom while still demonstrating the planning logic.

---

## 4. Preparation Phase: 12 Minutes

The frontend should explicitly support the project’s rehearsal flow:

| Time | Activity |
|---|---|
| 0:00–1:30 | Build a single-reading game and fallback plan. |
| 1:30–5:00 | Process fact rewordings, generate plans, cross-score candidates, and review strategic and ethical concerns. |
| 5:00–6:00 | Stop generation and assemble the brief from validated results. |
| 6:00–12:00 | The team reviews sources, checks assumptions, and chooses an opening and fallback. |

This means the UI needs a clear preparation workspace that supports:

- loading the case and source packet,
- reviewing source facts and contradictions,
- seeing the fallback plan before negotiation starts,
- comparing base and perturbed recommendation cards,
- finalizing a one-page brief with opening offer, walk-away point, red lines, and assumptions.

The one-page brief should be rendered as a structured panel with:

- trade-off table,
- opening offer,
- alternatives,
- walk-away point,
- red lines,
- critical assumptions,
- short contingent decision tree.

### 4.1 App shell

The app should have a three-panel layout:

- Left panel: scenario context and evidence
- Center panel: live negotiation simulation
- Right panel: strategy recommendations and decision brief

## 5. Live Negotiation Phase: 12–15 Minutes

One teammate should operate the interface while the others negotiate. The interface should support the live workflow exactly as the project plan describes, with optional voice capture for convenience and a required confirmation step before any state change:

1. Record an offer, response, or agreement using structured controls, with optional voice-to-text transcription for faster entry.
2. Confirm the parsed event before updating the game state.
3. Update commitments and beliefs about the opponent’s preferences.
4. Re-plan and display a next-move card with an offer, fallback, value estimates, and relevant flags.

The live simulation should therefore include:

- a turn log with structured event entry,
- a confirmation step before state mutation,
- a commitment tracker that updates only when the operator confirms the action,
- a next-move recommendation card after each round,
- a visible walk-away and fallback branch.

Perturbations run during prep only. No LLM is required for live action selection. Voice parsing may be used as an input convenience layer, but all speech must be converted into a structured event and confirmed before the state is mutated. A printed decision tree provides a fallback. Live classroom use follows course rules.

Disagreement across readings measures variation in the system’s interpretation. It is not automatically a calibrated probability distribution over human opponent types.

### 4.2 Left panel: preparation workspace

Contains:

- negotiation title / scenario name
- shared package details
- private role card
- objective summary
- red lines and non-negotiables
- key facts / issue list
- optional perturbation comparison panel
- “brief ready” checklist for the 12-minute preparation rhythm

This is the pre-planning workspace where the user reviews what matters before making a move.

### 4.3 Center panel: negotiation simulation

Contains:

- current turn number
- active proposer
- current offer / counteroffer
- action buttons: Accept, Reject, Counter, Walk Away
- suggested next move card
- commitment tracker
- unresolved issues list

The simulation should feel like a lightweight decision board, not a complex game engine.

### 4.4 Right panel: decision support

Contains:

- recommended opening offer
- fallback options
- likely opponent priorities
- estimated value trade-offs
- warnings and red-flag reasons
- explanation of why a recommendation is favored

This panel acts as the “advisor” view without pretending to be a full autonomous negotiator.

---

## 6. Perturbation / Pre-Planning Model

The project is studying rewording robustness, but for the front-end scaffold the perturbation is not live.

Instead:

- the model team generates a large perturbation set ahead of time,
- the front end loads a family of valid rewordings rather than a single comparison,
- the user can inspect how the same factual situation is framed differently across many variants,
- the app surfaces whether a recommendation is stable across the perturbation set.

The important design point is that this is not a one-vs-one comparison. The system is designed around a variable set of `K` rewordings, where `K` is the number of accepted meaning-preserving variants generated for a fact set or package. For the demo, `K` can be large enough to reveal sensitivity, but the classroom-facing interface should still present only a limited subset of the most important variants and summarize the rest in an admin view.

### Example interpretation types

- Original wording
- Paraphrased facts
- Ambiguity-sensitive phrasing
- High-precision wording
- Constraint-preserving version

### Example frontend behavior

- User toggles between “Base brief” and “Perturbed brief”
- System displays changes in facts, inferred priorities, or risk flags
- App warns: “Recommendation remains stable under rewording” or “Recommendation changes significantly across formulations”

This is a scaffold for classroom understanding: it demonstrates that meaning-preserving variation can affect negotiation advice without requiring a live rewording loop.

---

## 6.1 Separate admin view for many perturbations

The research workflow needs a separate admin-style view that is distinct from the classroom-facing negotiation workspace.

### Admin view responsibilities

- show the full perturbation set generated for a scenario,
- display how many valid rewordings were accepted,
- summarize stability across variants,
- surface the top few high-sensitivity facts or assumptions,
- let a researcher filter by rewording distance, topic, or issue,
- allow review of which variants caused recommendation changes.

### Classroom view responsibilities

- show a small, curated subset of perturbation variants,
- display only the most relevant stability indicators,
- avoid overwhelming the negotiators with a long list of rewordings,
- emphasize whether the selected strategy is robust.

This split is important because the real experiment is built around many perturbations, but the Monday classroom experience should remain clear and usable.

---

## 7. Core Data Model

The frontend should rely on a clean structured data contract. Minimal schema:

```json
{
  "scenarioId": "scenario-001",
  "title": "Humanitarian Supply Negotiation",
  "sharedPackage": [
    { "id": "fact-1", "text": "Aid convoy can reach the border next week.", "source": "source-doc-A" }
  ],
  "roleCard": {
    "team": "Our Team",
    "objectives": ["secure corridor access", "preserve delivery capacity"],
    "redLines": ["no agreement that compromises safety"],
    "priorityWeights": { "security": 0.4, "supply": 0.4, "political": 0.2 }
  },
  "strategyOptions": [
    {
      "id": "option-1",
      "name": "Opening concession",
      "summary": "Offer limited access in exchange for monitoring guarantees.",
      "risk": "medium"
    }
  ],
  "turns": [],
  "commitments": [],
  "walkAwayThreshold": 0.45
}
```

This design keeps the frontend simple while allowing different engine outputs to plug into the same UI.

---

## 8. State Management

The app should maintain a structured state object with:

- `scenario`
- `userRole`
- `facts`
- `strategyOptions`
- `activeStrategy`
- `turnState`
- `commitmentState`
- `eventLog`
- `decisionSummary`

Recommended state groups:

- prep state
- live simulation state
- summary state
- perturbation comparison state

This separation makes it easier to reset the simulation, review previous turns, and show a clean summary after class.

---

## 9. User Interaction Patterns

### 8.1 Preparation phase

- User loads scenario
- Reads role card
- Reviews facts and non-negotiables
- Compares strategies
- Chooses recommended approach

### 8.2 Live negotiation phase

- User enters an offer or selects a suggested packaged option
- System validates if the proposed move respects constraints
- User sees whether this move improves or harms value
- User advances to the next turn

### 8.3 Reflection phase

- Review outcome
- Inspect which commitments were accepted/rejected
- Compare base and perturbed strategy recommendations
- Export brief or summary for class discussion

---

## 10. Simulation Rules for Monday Demo

To keep the classroom demo robust and legible, use a simplified negotiation loop:

1. Each turn consists of one offer, one response, and one update.
2. A move can only add commitments that are consistent with the current state.
3. The system stores the timeline in order.
4. Users can see the current value of each issue and the overall deal quality.
5. Acceptance and rejection are manual, with the UI making it obvious when a proposal is outside the recommended range.
6. Walk-away is a first-class action, not a hidden rule.

The important classroom point is that the UI is supporting decision-making, not replacing it with automated bargaining.

---

## 11. Suggested Interface Components

### Negotiation card

- issue label
- status indicator (accepted / pending / rejected)
- preferred value / minimum value
- rationale explanation

### Recommendation card

- title
- summary
- risk level
- confidence
- why it may work
- associated perturbation set

### Event log entry

- turn number
- actor
- action
- effect on commitments
- notes

### Summary panel

- final agreement or deadlock
- value gained/lost
- concessions made
- recommended next step

---

## 12. Frontend Workflow Example

### Typical scenario

A team negotiates access, supplies, and monitoring conditions.

- Base recommendation: “Offer monitoring access first, then secure convoy access.”
- Perturbation comparison: “Alternative wording changes the urgency of the monitoring requirement.”
- User chooses to follow the base recommendation.
- User submits an opening offer.
- User receives response.
- UI highlights if the conditional branch is still valid.
- User decides whether to accept, reject, or reframe the offer.

This demonstrates how the system can help with decisions while leaving human judgment in charge.

---

## 13. Non-Goals for the Scaffold

This scaffold does not need to include:

- production-grade authentication
- real-time multiplayer networking
- full optimization engine
- live LLM negotiation generation during the class demo
- detailed policy or ethics enforcement beyond simple red-line warnings

The focus is clarity, speed, and educational demonstration.

---

## 14. Acceptance Criteria for the Scaffold

The scaffold is successful if it can:

- load a negotiation scenario,
- render the shared package and role card,
- show strategy options before negotiation,
- allow a user to simulate turn-by-turn offers,
- track a commitment state,
- display a clear summary after each decision,
- compare base and perturbed interpretations in a clean side-by-side view,
- remain understandable during a live classroom interaction.

---

## 15. Recommended MVP for Monday

For Monday’s class interaction, the best MVP is:

- one scenario,
- one role card,
- one set of strategy recommendations,
- a single structured negotiation panel,
- a comparison between base interpretation and one perturbation variant,
- a concise end-of-sim summary.

This is enough to demonstrate the project concept without overbuilding the front end before the model and engine are done.

---

## 16. Final Architecture Summary

The overall architecture should be:

- Human-centered UI for review and interaction
- Structured negotiation state rather than free-form chat
- Pre-planned perturbation comparison rather than live generation
- Strategy recommendation panel for decision support
- Simulation engine for turn tracking and commitment updates
- Notes and summary export for class discussion

This matches the project’s current scope: a scaffold built to help negotiation preparation and classroom demonstration, while the rewording engine, model reasoning, and output generation are developed separately.

---

## Visual design system and content rules

The UI should be designed as a data-driven research dashboard, not a set of hardcoded placeholders. Every label, badge, title, and case-specific string must render from scenario content rather than static demo text.

### Design principles

- All scenario names, stakeholder labels, and negotiation details come from the loaded materials.
- The interface must support different cases without editing the UI code.
- Colors, grid, and typography are fixed, while content remains dynamic.
- The research/admin view uses denser information architecture, while the classroom/live view is simplified and guided.

### Dynamic content model

Use fields from the scenario payload rather than hardcoded strings:

```json
{
  "scenario": {
    "title": "{{scenario.title}}",
    "subtitle": "{{scenario.subtitle}}",
    "context": "{{scenario.context}}",
    "participants": ["{{partyA.name}}", "{{partyB.name}}"],
    "documents": "{{scenario.sourceCount}} sources",
    "issueSet": "{{scenario.issueSet}}"
  },
  "role": {
    "team": "{{role.teamName}}",
    "objective": "{{role.objective}}",
    "redLines": "{{role.redLines}}",
    "priorityWeights": "{{role.priorityWeights}}"
  }
}
```

This ensures that labels like the scenario title, parties, objective, and red lines are always tied to the actual negotiation material rather than a placeholder such as "Alder University".

### Layout grid

Use a fixed desktop grid system for clarity and consistency:

- Shell width: 1440 px max
- Outer padding: 24 px
- 12-column grid
- Column gap: 20 px
- Row gap: 16 px
- Left column: 3 columns for evidence and context
- Center column: 6 columns for the live negotiation workspace
- Right column: 3 columns for recommendations and decisions

For tablet or small-screen layouts:

- collapse to 2-column layout
- keep decision support stacked beneath the negotiation board
- preserve the evidence drawer and summary panel as independent sections

### Color system

Use a restrained, professional palette with enough contrast for research use and live class demonstration.

- Background base: #F5F7F4
- Panel surface: #FFFFFF
- Panel alt surface: #EEF3F1
- Primary text: #12231D
- Secondary text: #4A5E59
- Border: #D7E0DD
- Accent primary: #1F7A67
- Accent secondary: #BFE2D7
- Warning: #B86B1A
- Warning soft: #F5E5D0
- Critical: #A13A2F
- Critical soft: #F8E3E1
- Focus ring: #1F7A67
- Highlighted recommendation: #EAF6F2

These colors should be semantic rather than decorative: primary = stable strategy, warning = changing assumptions, critical = red-line or high-risk move.

### Typography

- Heading 1: 28 px / 700 / strong research tone
- Heading 2: 20 px / 600
- Heading 3: 16 px / 600
- Body: 14 px / 400
- Metadata: 12 px / 500
- Label / tag: 11 px / 600 uppercase tracking

Use consistent hierarchy across both the admin and classroom views:

- Scenario title at top of each major panel
- Sharable labels for issue, source, and recommendation cards
- Compact values for priority, risk, and confidence indicators

### Panel structure

#### Left panel: evidence and context

- negotiation title
- scenario subtitle
- source count and document coverage
- role card
- objective summary
- critical facts
- red lines
- issue / topic chips

#### Center panel: negotiation board

- current turn
- active participant
- offer / counteroffer state
- acceptance, rejection, and counter actions
- commitment tracker
- event log
- structured confidence or rationale panel

#### Right panel: analytical support

- recommended move
- fallback strategy
- sensitivity / perturbation summary
- confidence and stability indicator
- risk notes
- assumptions to review

### Admin / research view content rules

The admin panel should not be a simplified demo. It should show:

- full perturbation set
- generated rewording count
- variant stability score
- issue sensitivity list
- recommendation drift across variants
- reasons why one strategy remains robust or changes under wording

Headlines should be written dynamically from the scenario and issue names, for example:

- "How wording shifts the {{issue.name}} decision"
- "{{scenario.title}} perturbation summary"
- "Stability across {{variantCount}} rewordings"

### Classroom / live view content rules

The classroom-facing view should present a small curated subset only:

- current offer
- current gain / loss
- risk and red-line alerts
- one recommended move
- one fallback option
- one confirm-before-submit action

It should avoid exposing the full perturbation engine to the negotiators. The only visible summary should be a compact statement such as:

- "This recommendation remains stable across the most relevant variants"
- "This recommendation is sensitive to wording changes"
- "Counterparty interpretation may shift under alternate phrasing"

These lines should be generated from the scenario state, not typed as static classroom copy.

### Interaction and confirmation pattern

Voice can still be supported as an input convenience layer, but regardless of input source the app must convert speech or free text into a structured event before updating state.

Required flow:

1. Capture raw input
2. Parse into event object
3. Display interpretation summary
4. User confirms or edits the parsed action
5. Commit state change

This avoids hardcoded assumptions and keeps the system aligned with the actual negotiation material.

---

## Exact Figma-style screen specification

This section converts the scaffold into a concrete screen-by-screen design brief suitable for Figma, with layout, component hierarchy, and data-driven content rules.

### Screen 1: Preparation workspace

Purpose: let a user review the case, role, facts, strategy, and perturbation sensitivity before entering the live negotiation.

#### Layout

- Frame size: 1440 x 980
- Background: #F5F7F4
- Top bar: 72 px height, full width
- Left panel: 320 px width
- Center panel: flexible main area
- Right panel: 360 px width

#### Top bar

- left: scenario name, subtitle, and case status chip
- center: time indicator for the 12-minute prep phase
- right: role switch, document count, and export actions

#### Left panel: evidence and role

- title: "Case Overview"
- scenario headline from data
- role card with team name, objectives, and red lines
- source documents list with type and count
- issue chips with current focus areas
- small summary card: "Risk profile" and "Priority weights"

#### Center panel: main prep board

- section header: "Negotiation Brief"
- status summary strip with objective, walk-away threshold, and current recommendation
- strategy cards in a two-column grid
- each card includes:
  - strategy name
  - confidence indicator
  - key tradeoff
  - risk level
  - variant count / stability tag
- lower section: "Perturbation Snapshot" with 3–4 most relevant wording variants
- a final CTA: "Ready to negotiate"

#### Right panel: decision support

- title: "Current recommendation"
- selected strategy summary with score and rationale
- key assumptions list
- sensitivity summary
- disputed issue list
- action button group: "Compare variants", "Review sources", "Finalize brief"

#### Interaction behavior

- selecting a strategy card updates the recommendation summary
- toggling a perturbation variant updates the rationale panel
- if the recommendation is unstable, the card shows a warning state

### Screen 2: Live negotiation board

Purpose: conduct a turn-based classroom negotiation with structured actions and optional voice capture.

#### Layout

- Frame size: 1440 x 980
- three-column arrangement matching the prep layout
- center panel remains largest

#### Left panel: evidence and facts

- title: "Case facts"
- selected issue list
- evidence chips with source attribution
- key constraints and red-line status
- collapsible source drawer for deep review

#### Center panel: live negotiation surface

- top: turn counter + active responder + timer
- offer area: current proposal card with issue chips and values
- action row: Accept, Reject, Counter, Walk Away
- if voice is enabled, a floating voice capture panel appears at the top or bottom
- structured event composer with fields:
  - action type
  - actor
  - issue
  - value
  - rationale
- event log timeline on the lower section

#### Right panel: advisor and risk

- current recommendation summary
- fallback move
- risk and confidence indicators
- suggestion bubble: "Likely response pattern" or "Counterparty reinterpretation"
- next-move card with a concise recommendation

#### State behaviors

- Accept / Reject / Counter updates the commitment tracker only after confirmation
- voice transcript is parsed into structured fields before commit
- if parsed event differs from user intent, a confirmation modal appears

### Screen 3: Event confirmation modal

Purpose: prevent a raw voice or text entry from mutating the negotiation state without review.

#### Modal layout

- modal size: 540 x 360
- header: "Review parsed event"
- body shows:
  - detected action
  - actor
  - issue / value summary
  - proposed effect on commitments
- editing controls for the parsed fields
- buttons: "Cancel", "Edit", "Confirm"

#### Visual treatment

- modal dims the background
- the event summary cards use neutral surfaces
- the confirm button uses the primary accent
- the cancel button uses a ghost style

This screen should be a required checkpoint for any speech-driven action.

### Screen 4: Admin / research perturbation dashboard

Purpose: show the full perturbation analysis behind the classroom view without cluttering the negotiation board.

#### Layout

- Frame size: 1440 x 980
- top summary row with metrics
- left rail: 260 px with variant filters
- center: list/grid of perturbation variants
- right: issue sensitivity panel and recommendation drift

#### Top summary row

- total perturbations generated
- stability score
- high-sensitivity issues
- recommendation-change count

#### Left rail filters

- variant count slider
- issue filter chips
- source type filter
- stability threshold selector
- sensitivity toggle

#### Center panel: perturbation list

- each row has:
  - variant name or ID
  - paraphrased issue statement
  - stability tag
  - recommendation impact
  - whether it changed strategy or not

#### Right panel

- issue sensitivity ranking
- key wording differences across variants
- recommended move drift
- “why this still holds” / “why it changes” summaries

This screen should prioritize analytical clarity over conversational flow.

### Component-level design notes

#### Cards

- radius: 12 px
- shadow: subtle, low contrast
- border: 1 px solid #D7E0DD
- padding: 16 px
- default state and hover state should be distinct but minimal

#### Buttons

- primary: filled green
- secondary: outlined neutral
- danger: filled red for walk-away or red-line violations
- small chips for issue tags and filters

#### Status indicators

- stable: green label / soft green background
- sensitive: amber label / soft amber background
- critical: red label / soft red background

### Empty and warning states

- No sources loaded: show skeleton placeholders and missing data states
- No active recommendation: display neutral card requiring the user to finalize a brief
- Recommendation unstable: highlight with warning border and explanatory note
- Voice parse uncertain: show a review state before committing

### Fidelity expectations for Figma

The design should be built as a system of reusable components:

- Case summary card
- Role card
- Strategy recommendation card
- Offer card
- Event log item
- Status badge
- Perturbation row
- Confirmation modal

Each component should support states for default, hover, active, selected, warning, and critical.

### Final design intent

The final experience should feel like a polished research tool and a classroom-ready negotiation simulator at the same time:

- structured, data-rich prep workspace
- clear live action flow with human confirmation
- condensed classroom view with only the essential information
- separate full analytical view for researchers and instructors

This is the right design boundary for the project and is consistent with the research goal of measuring how wording shifts strategy without sacrificing usability in class.

---

## Figma wireframe hierarchy and naming convention

Use the following exact naming structure for the Figma frames and nested layers so the design is consistent and easy to hand off.

### Screen hierarchy

- Frame 01 — Prep Workspace
  - Header Bar
    - Scenario Title
    - Scenario Subtitle
    - Prep Timer
    - Role Switch
    - Source Count
  - Left Rail — Evidence & Role
    - Case Overview
    - Role Card
    - Red Lines
    - Source List
    - Issue Chips
  - Center Workspace — Brief & Strategy
    - Section Header: Negotiation Brief
    - Objective Summary Row
    - Strategy Card Grid
      - Strategy Card 01
      - Strategy Card 02
      - Strategy Card 03
    - Perturbation Snapshot
      - Variant Row 01
      - Variant Row 02
      - Variant Row 03
    - Finalize CTA
  - Right Rail — Recommendation
    - Recommendation Summary
    - Key Assumptions
    - Sensitivity Summary
    - Disputed Issues
    - Action Group

- Frame 02 — Live Negotiation Board
  - Header Bar
    - Turn Counter
    - Active Party
    - Event Timer
    - Voice Capture Toggle
  - Left Rail — Case Facts
    - Fact List
    - Source Attributions
    - Constraints
    - Red Line Status
  - Center Workspace — Offer & Response
    - Current Offer Card
    - Issue Value Stack
    - Action Row
      - Accept
      - Reject
      - Counter
      - Walk Away
    - Event Log
    - Proposed Update Summary
  - Right Rail — Advisor
    - Recommended Move
    - Fallback Move
    - Risk / Stability Indicator
    - Next Move Card
    - Counterparty Interpretation

- Frame 03 — Voice Parse Confirmation Modal
  - Modal Header
    - Review Parsed Event
  - Parsed Event Summary
    - Detected Action
    - Actor
    - Value / Issue
    - Commitments Impact
  - Edit Controls
  - Footer Actions
    - Cancel
    - Edit
    - Confirm

- Frame 04 — Admin / Research Dashboard
  - Header Bar
    - Scenario Title
    - Perturbation Metrics
  - Left Filter Rail
    - Variant Count
    - Stability Threshold
    - Issue Filter
    - Source Filter
  - Center Analysis Panel
    - Perturbation Table
      - Variant Row
      - Impact Tag
      - Stability Tag
    - Recommendation Drift Summary
  - Right Insight Panel
    - Sensitivity Ranking
    - High-Impact Wording Changes
    - Recommendation Stability Summary

### Naming rules

- Frame names should be title case and descriptive.
- Panel names should be explicit and avoid generic terms like “panel” unless necessary.
- Component names should indicate role and state, e.g.:
  - Strategy Card — Selected
  - Variant Row — Warning
  - Recommendation Summary — Stable
  - Offer Card — Counterproposal

### Section-label rules

Every section should use high-clarity labels, such as:

- Case Overview
- Negotiation Brief
- Current Recommendation
- Case Facts
- Event Log
- Recommendation Drift
- Sensitivity Ranking
- Review Parsed Event

These labels should be fixed in the design system and not replaced by ad hoc copy.

This is the cleanest handoff structure for Figma: a small, reusable set of named frames and nested sections tied directly to the actual negotiation workflow.

---

## Low-fidelity wireframe layout spec

This version is intentionally lower fidelity than a polished UI spec. It gives the design team practical spacing, sizing, and section proportions so they can build the first pass quickly without locking in final visual decisions.

### Global wireframe tokens

- Canvas size: 1440 x 980
- Outer margin: 24 px
- Section spacing: 16 px
- Card radius: 12 px
- Card padding: 16 px
- Border weight: 1 px
- Header height: 72 px
- Minor gutter: 8 px
- Major gutter: 20 px

### Frame 01 — Prep Workspace

#### Page geometry

- Full canvas: 1440 x 980
- Top bar: 72 px height
- Left rail: 320 px width
- Center area: flexible width
- Right rail: 360 px width

#### Internal spacing

- vertical stacking between cards: 16 px
- horizontal spacing between cards in center grid: 16 px
- top padding inside each section: 20 px
- section heading to content gap: 12 px

#### Left rail

- Case Overview card: 320 x 180
- Role Card: 320 x 180
- Red Lines: 320 x 120
- Source List: 320 x 180
- Issue Chips: 320 x 60

#### Center area

- Negotiation Brief header: 24 px height
- Summary row: 72 px height
- Strategy Grid: 2 columns by 2 rows, each card approx 280 x 180
- Perturbation Snapshot: 240 px height
- Finalize CTA: 56 px height, full width within section

#### Right rail

- Recommendation Summary: 360 x 220
- Key Assumptions: 360 x 120
- Sensitivity Summary: 360 x 120
- Disputed Issues: 360 x 120
- Action Group: 360 x 80

### Frame 02 — Live Negotiation Board

#### Page geometry

- Full canvas: 1440 x 980
- Top bar: 72 px height
- Left rail: 300 px width
- Center workspace: 640 px width
- Right rail: 360 px width

#### Left rail

- Case Facts header: 40 px height
- Fact list: variable height, stacked list with 12 px rows
- Source Attributions: 150 px height
- Constraints: 150 px height
- Red Line Status: 120 px height

#### Center workspace

- Offer Card: 600 x 180
- Issue Value Stack: 600 x 220
- Action Row: 600 x 64
- Event Log: 600 x 200
- Proposed Update Summary: 600 x 120

#### Right rail

- Recommended Move: 360 x 160
- Fallback Move: 360 x 120
- Risk / Stability Indicator: 360 x 90
- Next Move Card: 360 x 150
- Counterparty Interpretation: 360 x 100

### Frame 03 — Voice Parse Confirmation Modal

#### Modal geometry

- width: 520 px
- height: approx 360 px
- border radius: 16 px
- inset padding: 20 px
- footer height: 64 px

#### Key regions

- Header: 52 px height
- Event Summary: 140 px height
- Edit Controls: 100 px height
- Footer Actions: 64 px height with 2 buttons aligned right

#### Standard spacing

- 16 px between rows within the summary
- 20 px between sections
- 12 px padding around fields

### Frame 04 — Admin / Research Dashboard

#### Page geometry

- Full canvas: 1440 x 980
- Top summary row: 120 px height
- Left filter rail: 260 px width
- center analysis: flexible width
- right insight panel: 300 px width

#### Top summary row

- four metric tiles, each approx 180 x 80
- spacing between tiles: 16 px

#### Left rail

- Variant Count: 180 x 80
- Stability Threshold: 180 x 80
- Issue Filter: 180 x 120
- Source Filter: 180 x 120

#### Center analysis panel

- table header: 36 px height
- each row: 56 px height
- 12 px vertical spacing between rows
- recommended details block: 220 px height

#### Right insight panel

- Sensitivity Ranking: 260 x 160
- High-Impact Wording Changes: 260 x 180
- Recommendation Stability Summary: 260 x 160

### Layout principles for the low-fidelity pass

- Keep the three-column app shell consistent across prep and live screens.
- Maintain clear hierarchy with predictable spacing and vertical rhythm.
- Show content density differently between admin and classroom modes.
- Build cards with consistent dimensions so the design system can be reused later.
- Treat the admin screen as denser and more analytical than the live negotiation board.

### Recommended wireframe behavior

- The prep screen should feel like a guided brief before the action begins.
- The live screen should be more operational and action-focused.
- The admin view should feel like a detailed analysis panel, not a classroom UI.
- The confirmation modal should appear as an interrupt state only when a user action needs validation.

This low-fidelity layout is meant to capture the right structure and hierarchy before final styling or color polish.

---

## Detailed UI specification: text hierarchy and component states

This section defines the exact content hierarchy and interaction states needed to move the wireframes into a polished UI system.

### Typography hierarchy

#### Page title

- size: 28 px
- weight: 700
- line height: 34 px
- color: #12231D
- usage: top-level scenario and section titles

#### Screen subtitle

- size: 14 px
- weight: 500
- line height: 20 px
- color: #4A5E59
- usage: scenario context and supporting description

#### Section header

- size: 18 px
- weight: 600
- line height: 24 px
- color: #12231D
- usage: Case Overview, Negotiation Brief, Event Log, etc.

#### Card title

- size: 16 px
- weight: 600
- line height: 22 px
- color: #12231D
- usage: strategy names, issue names, recommendation labels

#### Body text

- size: 14 px
- weight: 400
- line height: 20 px
- color: #12231D
- usage: fact text, rationale, summaries

#### Metadata text

- size: 12 px
- weight: 500
- line height: 16 px
- color: #4A5E59
- usage: labels, tags, counts, time metadata

#### Button label

- size: 14 px
- weight: 600
- line height: 20 px
- usage: actions like Accept, Counter, Confirm, Finalize

### General text rules

- No sentence should be hardcoded to a fictional scenario.
- Scenario-level labels are loaded from the current negotiation data object.
- Use title case for section labels and sentence case for body text.
- Keep long rationale text in a secondary line beneath the main label.
- Expose only essential facts in the classroom interface; use more detail in the admin view.

### Component states

#### Strategy card states

- default: white background, standard border, neutral text
- hover: subtle border color change, lift shadow, darkened text
- selected: accent border, green background highlight, strong contrast text
- warning: amber border, amber badge, caution icon
- critical: red border, red badge, strong alert label

#### Recommendation summary

- default: neutral panel with summary title and score
- stable: green accent bar and “Stable across variants” label
- sensitive: amber accent bar and “Wording-sensitive” label
- critical: red accent bar and “High-risk interpretation” label

#### Offer card states

- draft: neutral surface with empty or editable values
- reviewed: border accent, parsed values visible
- confirmed: green border or success badge after approval
- rejected: red border and reason badge

#### Event log item states

- pending: neutral tone
- confirmed: primary accent
- edited: blue/grey accent
- rejected: red accent

#### Action button states

- default: neutral or filled depending on intent
- hover: slight color deepening
- disabled: low opacity, no pointer events
- active: pressed style with stronger contrast

### Interaction state language

Use these exact interaction labels in the design system:

- Default
- Hover
- Active
- Selected
- Disabled
- Warning
- Critical
- Confirmed
- Draft
- Review Required

This keeps the design language consistent across screens and reduces ambiguity for engineering handoff.

### UI states by screen

#### Prep Workspace

- Strategy card selected = user finalizes one recommendation
- Variant row selected = user drills into a wording alternative
- Finalize CTA = enabled only if the brief has enough facts and a recommendation
- Warning state = triggered if the recommendation changes across top variants

#### Live Negotiation Board

- Action buttons are disabled until a valid offer is present
- Confirm button remains disabled until parsed event is reviewed
- Warning state appears when the user attempts a move outside the recommended action range
- Counterparty interpretation label updates when the issue framing changes

#### Confirmation Modal

- Cancel = closes without committing state change
- Edit = opens direct editing fields for the parsed event
- Confirm = commits the structured event and updates the negotiation state
- Review required = state if the system is uncertain about the parsed action

#### Admin Dashboard

- Filter chips update both the variant table and the sensitivity panel
- Map of recommendation drift updates instantly when the threshold changes
- Stable / warning / critical states correspond to the all-variant sensitivity summary

### Content hierarchy examples

#### Prep screen example

- Title: {{scenario.title}}
- Subtitle: {{scenario.subtitle}}
- Card title: {{strategy.name}}
- Supporting text: {{strategy.summary}}
- Metadata: {{strategy.risk}} • {{variantCount}} variants
- CTA: Finalize brief

#### Live negotiation example

- Title: Current offer
- Supporting text: {{issue.name}} • {{value}} • {{party.name}}
- Action label: Counter
- Risk label: Wording sensitive
- Summary line: “Recommendation remains stable across the most relevant variants.”

#### Admin example

- Title: Recommendation drift
- Metric label: Stability score
- Supporting text: {{stableVariantCount}} / {{totalVariantCount}} variants remain aligned
- Alert label: High-impact wording change

### Design system rules

- Use semantic color only, not decorative color.
- Keep all warnings readable in both the classroom and admin experiences.
- Do not display all perturbation detail in the classroom flow.
- Keep cards within a consistent vertical rhythm to reduce cognitive load.
- Use the same interaction language everywhere: Default, Warning, Selected, Confirmed, Critical.

### Final specification summary

The final UI should feel like a guided negotiation workspace with two layers:

1. Classroom-facing live negotiation surface with high clarity and minimal noise
2. Research-facing admin dashboard with full perturbation detail and instability analysis

Both surfaces share the same core structure, card language, and interaction states, while the classroom view intentionally reduces content density.

This is the final state needed before implementation or Figma design polish.

### Recommended interface copy

The overall product phrases should stay generic and scenario-driven rather than hardcoded to a demo case.

- Headline pattern: "See how wording changes the strategy"
- Subhead pattern: "{{scenario.title}} • {{participantCount}} parties • {{sourceCount}} sources"
- Summary line pattern: "Same facts. Different wording."
- Supporting text pattern: "Wording may shift interpretation and strategy. The evidence and constraints remain fixed."

The design should be purposeful, research-credible, and classroom-usable without ever requiring scenario-specific placeholder text like a fictional university and institution name.

This is the right direction for the front-end: a reusable system with a fixed visual language and dynamic scenario content that follows the actual materials being negotiated.
