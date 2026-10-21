/**
 * Perturbation-Robust Negotiation Advisor — static UI from Figma mockup
 */

const state = {
  view: "prep", // prep | classroom | admin
  classroomMode: "live", // live | voice
};

const ICON = (name, w, h) =>
  `<img class="icon" src="assets/icons/${name}.svg" width="${w || 16}" height="${h || 16}" alt="" />`;

function pill(type, label) {
  return `<span class="pill pill-${type}"><span class="pill-dot"></span>${label}</span>`;
}

function advisoryBar(body) {
  return `
    <div class="advisory-bar">
      <div class="lock-title">${ICON("d3a4d", 17, 17)} Same facts. Different wording.</div>
      <span class="sep"></span>
      <p class="body">${body}</p>
      <span class="tag">ADVISORY · YOU DECIDE</span>
    </div>`;
}

function evidencePanel(extraBottom = "", wrapAside = true) {
  const inner = `
      <div class="panel-label"><span>EVIDENCE &amp; BOUNDARIES</span><span class="mono">FIXED</span></div>
      <div class="card">
        <h3>Your role</h3>
        <p class="sub">Buyer · Alder University</p>
        <div class="role-row">
          <div class="org-mark">${ICON("e1ba3", 21, 21)}</div>
          <div>
            <strong>Lab procurement lead</strong>
            <span>Opposite Cedar Instruments</span>
          </div>
        </div>
        <p>Secure 24 air-quality sensors for the autumn field study.</p>
      </div>
      <div class="card">
        <h3>Evidence ledger</h3>
        <p class="sub">Case packet v1.0 · read-only</p>
        ${pill("live", "Facts verified · 4 / 4")}
        <div style="height:16px"></div>
        ${factRow("F1", "Supplier quote", "$24,000 for 24 sensors")}
        ${factRow("F2", "Buyer budget cap", "$22,800 total")}
        ${factRow("F3", "Delivery requirement", "By 30 September")}
        ${factRow("F4", "Warranty requirement", "12 months")}
        <hr class="divider" />
        <div class="link-row">${ICON("6f7d5", 14, 14)} Open original case packet ↗</div>
      </div>
      <div class="card card-muted">
        <h3>Private boundaries</h3>
        <div class="boundary-row"><span>Target / opening</span><strong>$21,600 / $20,400</strong></div>
        <p>Do not exceed $22,800 or trade away delivery and warranty requirements.</p>
        <hr class="divider" />
        <p class="fallback-label">FALLBACK · NORTHSTAR</p>
        <p>$22,560 · delivery 14 October. Within budget, but 14 days late.</p>
        ${extraBottom}
      </div>`;
  return wrapAside ? `<aside class="col-evidence">${inner}</aside>` : inner;
}

function factRow(id, label, value) {
  return `
    <div class="fact-row">
      <span class="fid">${id}</span>
      <div>
        <p class="flabel">${label}</p>
        <p class="fvalue">${value}</p>
      </div>
    </div>`;
}

function appNav() {
  const tabs = [
    { id: "prep", label: "Prep" },
    { id: "classroom", label: "Classroom / Negotiation" },
    { id: "admin", label: "Admin / Research" },
  ];
  return `
    <header class="app-nav">
      <div class="brand">
        <div class="brand-mark">${ICON("6100c", 22, 22)}</div>
        <div class="brand-text">
          <p class="name">Perturbation-Robust</p>
          <p class="tagline">NEGOTIATION ADVISOR</p>
        </div>
      </div>
      <nav class="workspace-nav" aria-label="Workspace">
        ${tabs
          .map(
            (t) =>
              `<button type="button" class="tab-btn${state.view === t.id ? " active" : ""}" data-view="${t.id}">${t.label}</button>`
          )
          .join("")}
      </nav>
      <div class="seminar-id">
        ${pill("neutral", "Seminar demo")}
        <div class="avatar" aria-hidden="true">AL</div>
      </div>
    </header>`;
}

function footer(left) {
  return `
    <footer class="app-footer">
      <span class="mono">${left}</span>
      <span>Human-led negotiation · No autonomous commitments</span>
    </footer>`;
}

function variantCards(compact) {
  const cards = [
    {
      id: "V017 · Gap made explicit",
      status: ["stable", "Stable"],
      quote:
        "“Our $22,800 budget is $1,200 below the $24,000 quote. Delivery is required by 30 September, with a 12-month warranty.”",
      interp: "Interpretation: a price gap to explore.",
      move: "Ask about price flexibility.",
      warm: false,
    },
    {
      id: "V042 · Schedule first",
      status: ["sensitive", "Sensitive"],
      quote:
        "“Delivery by 30 September and a 12-month warranty are required. The quote is $24,000; our budget is capped at $22,800.”",
      interp: "Priority shifts toward delivery certainty.",
      move: "Ask about price flexibility; verify delivery.",
      warm: false,
    },
    {
      id: "V084 · Gap minimized",
      status: ["changed", "Recommendation changed"],
      quote:
        "“Only $1,200 separates our $22,800 budget cap from the $24,000 quote. Delivery is required by 30 September, with a 12-month warranty.”",
      interp: "Interpretation: the gap feels easy to close.",
      move: "Offer a price concession earlier.",
      warm: true,
      warn: true,
    },
  ];
  if (compact) {
    return `<div class="lens-mini">${cards
      .map(
        (c) => `
      <div class="item${c.warm ? " hot" : ""}">
        <div class="variant-id">${c.id}</div>
        ${pill(c.status[0], c.status[1])}
      </div>`
      )
      .join("")}</div>`;
  }
  return `<div class="variant-grid">${cards
    .map(
      (c) => `
    <div class="variant-card${c.warm ? " warm" : ""}">
      <div>
        <p class="variant-id">${c.id}</p>
        ${pill(c.status[0], c.status[1])}
      </div>
      <p class="variant-quote">${c.quote}</p>
      <hr class="divider" style="margin:0" />
      <div class="variant-effect">
        <p>${c.interp}</p>
        <strong class="${c.warn ? "warn" : ""}">${c.move}</strong>
      </div>
    </div>`
    )
    .join("")}</div>`;
}

function guidancePanel(prep) {
  const title = prep ? "REHEARSAL GUIDANCE" : "DECISION SUPPORT";
  const headline = prep ? "Ask before you concede." : "Trade conditionally. Keep the date.";
  const body = prep
    ? "Clarify price flexibility while holding delivery and warranty constant. Do not treat a small gap as a reason to pay more."
    : "Your draft offers $21,800 with delivery and warranty unchanged. Cedar’s last confirmed offer is $22,600. Hold the date; trade only with verified conditions.";
  const foot = prep
    ? "Useful across the three classroom variants."
    : "Aligned with stable variants V017 and V042.";

  return `
    <aside class="col-side">
      <div class="panel-label"><span>${title}</span><span class="mono">ADVISORY</span></div>
      <div class="card card-dark guidance-dark">
        <div class="eyebrow-row">${ICON("e5e80", 18, 18)} ROBUST NEXT MOVE</div>
        <h2>${headline}</h2>
        <p>${body}</p>
        <hr class="divider" />
        <p class="foot">${foot}</p>
      </div>
      <div class="card">
        <h3>Wording risk signals</h3>
        ${pill("sensitive", "Sensitive to gap framing")}
        <p style="margin:16px 0">“Only $1,200” can make a concession feel inevitable. It adds no new evidence.</p>
        <hr class="divider" />
        <div class="risk-row">
          ${ICON("b5384", 18, 18)}
          <div>
            <strong>1 of 3 variants changes strategy</strong>
            <p class="note-sm" style="margin:4px 0 0">V084 favors an early price concession. Verify intent before following it.</p>
          </div>
        </div>
      </div>
      <div class="card card-muted">
        <h3>If the price stalls</h3>
        <p>Ask whether payment timing can support a lower price. Do not promise terms without authority.</p>
        <p>If no compliant agreement is possible, pause and seek a schedule exception for Northstar.</p>
      </div>
      <div class="human-reminder">
        ${ICON("f8f12", 17, 17)}
        <span>Suggestions never send themselves. Review and confirm every state change.</span>
      </div>
    </aside>`;
}

function phaseTimeline() {
  const phases = [
    { name: "Open", range: "0–3 min", done: true },
    { name: "Explore · now", range: "3–8 min", done: true, active: true },
    { name: "Package", range: "8–12 min", done: false },
    { name: "Close", range: "12–15 min", done: false },
  ];
  return `
    <div class="time-card">
      <div class="session-clock">
        ${ICON("b53d1", 22, 22)}
        <div>
          <p class="clock-main">06:40 <span>/ 14:00</span></p>
          <p class="clock-sub">7:20 remaining · 12–15 min exercise</p>
        </div>
      </div>
      <div class="phase-timeline">
        ${phases
          .map(
            (p) => `
          <div class="phase">
            <div class="phase-bar${p.done ? " done" : ""}"></div>
            <div class="phase-labels">
              ${p.active ? `<strong>${p.name}</strong>` : `<span>${p.name}</span>`}
              <span class="mono">${p.range}</span>
            </div>
          </div>`
          )
          .join("")}
      </div>
      <button type="button" class="btn">${ICON("cd4e3", 16, 16)} Pause session</button>
    </div>`;
}

function prepView() {
  return `
    <main class="workspace">
      <div class="page-intro">
        <div class="copy">
          <p class="eyebrow">ALDER × CEDAR  /  AQ-24  /  BUYER REHEARSAL</p>
          <h1 class="page-title">Prepare for the conversation.</h1>
          <p class="page-subtitle">A 12-minute rehearsal to separate what you know from how it is framed.</p>
        </div>
        <button type="button" class="btn">Save &amp; exit</button>
      </div>
      <div class="step-row">
        ${stepCard("✓", "Read your role", "0–2 min · Complete", false, true)}
        ${stepCard("02", "Compare wording", "2–6 min · In progress", true)}
        ${stepCard("03", "Test your opening", "6–10 min · Up next", false)}
        ${stepCard("04", "Confirm your plan", "10–12 min · Then go live", false)}
      </div>
      ${advisoryBar("Wording may shift interpretation and strategy. Evidence and constraints stay fixed.")}
      <div class="three-col">
        ${evidencePanel('<p class="note-sm">Fallback is not equivalent: escalate the schedule exception before accepting.</p>')}
        <section class="col-main">
          <div class="panel-label"><span>COMPARE WORDING</span><span class="mono">STEP 02 / 04</span></div>
          <div class="card">
            <div class="activity-head">
              <div>
                <h2>What changes when the wording changes?</h2>
                <p>Read the same evidence through three lenses.</p>
              </div>
              ${pill("neutral", "4 min exercise")}
            </div>
            <div class="baseline-box">
              <div class="baseline-head">${ICON("599e4", 15, 15)} BASELINE · FACTS F1–F4</div>
              <p>“The quote is $24,000. Our budget is capped at $22,800; delivery is required by 30 September, with a 12-month warranty.”</p>
            </div>
            <div style="height:20px"></div>
            ${variantCards(false)}
            <div class="filter-note" style="margin-top:16px">
              ${ICON("b2b99", 15, 15)}
              <span>3 of 128 pre-generated variants, selected to show stability, priority sensitivity and a strategy reversal. All preserve F1–F4.</span>
            </div>
          </div>
          <div class="card">
            <div class="row-actions" style="margin-bottom:16px">
              <h3 style="margin:0">Choose a robust opening</h3>
              ${pill("neutral", "Draft saved")}
            </div>
            <div class="opening-selected">
              ${ICON("726bd", 18, 18)}
              <span>“Where is there flexibility on price if delivery and warranty remain unchanged?”</span>
            </div>
            <div class="row-actions" style="margin-top:16px">
              <button type="button" class="btn">Back to role</button>
              <button type="button" class="btn btn-primary" data-view="classroom">${ICON("1d759", 16, 16)} Continue to test opening</button>
            </div>
          </div>
        </section>
        ${guidancePanel(true)}
      </div>
    </main>
    ${footer("Case AQ-24 · Session S-07 · illustrative classroom data")}`;
}

function stepCard(num, title, meta, active, done) {
  return `
    <div class="step-card${active ? " active" : ""}">
      <div class="step-num">${num}</div>
      <div>
        <p class="step-title">${title}</p>
        <p class="step-meta">${meta}</p>
      </div>
    </div>`;
}

function classroomLiveView() {
  return `
    <main class="workspace">
      <div class="classroom-toggle">
        <button type="button" class="tab-btn active" data-classroom="live">Live negotiation</button>
        <button type="button" class="tab-btn" data-classroom="voice">Voice event review</button>
      </div>
      <div class="page-intro">
        <div class="copy">
          <p class="eyebrow">SESSION S-07  /  ROUND 01  /  BUYER VIEW</p>
          <h1 class="page-title">Negotiate with the facts in view.</h1>
          <p class="page-subtitle">Alder University × Cedar Instruments · 24 air-quality sensors</p>
        </div>
        <div class="intro-actions">
          ${pill("live", "Live · Explore")}
          <button type="button" class="btn">End &amp; debrief</button>
        </div>
      </div>
      ${phaseTimeline()}
      ${advisoryBar("Wording may shift interpretation and strategy. Evidence and constraints stay fixed.")}
      <div class="three-col">
        ${evidencePanel()}
        <section class="col-main">
          <div class="panel-label"><span>LIVE CONVERSATION</span><span class="mono">4 CONFIRMED TURNS</span></div>
          <div class="card">
            <div class="row-actions" style="margin-bottom:14px">
              <h3 style="margin:0">Explore the price gap</h3>
              <span class="note-sm">Simulation · turn-based</span>
            </div>
            ${turn("01:40", "You · Alder University", "“We can open at $20,400 for all 24 sensors, with delivery by 30 September and a 12-month warranty.”", false)}
            ${turn("03:10", "Cedar Instruments", "“We can reduce the quote to $23,200. The delivery date and warranty would remain unchanged.”", false)}
            ${turn("04:45", "You · Alder University", "“Could we reach $21,600 while keeping delivery and the 12-month warranty as specified?”", false)}
            ${turn("06:20", "Cedar Instruments", "“Our revised offer is $22,600, delivered by 30 September, with a 12-month warranty.”", true)}
            <div class="state-line">${ICON("689a4", 15, 15)} State v4 · Supplier offer $22,600 · No agreement yet</div>
          </div>
          <div class="card card-accent-border">
            <div class="row-actions" style="margin-bottom:14px">
              <h3 style="margin:0;font-size:16px">Your next move</h3>
              ${pill("neutral", "Draft · not sent")}
            </div>
            <div class="draft-area">We can offer $21,800, conditional on delivery by 30 September and the 12-month warranty. Is that workable?</div>
            <div class="row-actions">
              <button type="button" class="btn" data-classroom="voice">${ICON("c8914", 16, 16)} Optional voice input</button>
              <div style="display:flex;gap:10px">
                <button type="button" class="btn">Edit draft</button>
                <button type="button" class="btn btn-primary">${ICON("1d759", 16, 16)} Review &amp; send</button>
              </div>
            </div>
            <p class="note-sm">Review creates a structured event. Only your confirmation updates the state.</p>
          </div>
          <div class="card">
            <div class="row-actions" style="margin-bottom:14px">
              <h3 style="margin:0;font-size:16px">Wording lens · case framing</h3>
              <span class="note-sm">Curated 3 / 128 · facts locked</span>
            </div>
            ${variantCards(true)}
            <p class="note-sm" style="margin-top:14px">Same draft, three framings. V084 would nudge an earlier concession—check that matches your intent.</p>
          </div>
        </section>
        ${guidancePanel(false)}
      </div>
    </main>
    ${footer("Case AQ-24 · Session S-07 · illustrative classroom data")}`;
}

function turn(time, speaker, text, highlight) {
  return `
    <div class="turn">
      <div class="turn-time">
        <p class="t">${time}</p>
        <div class="turn-dot${highlight ? " active" : ""}"></div>
      </div>
      <div class="turn-bubble${highlight ? " highlight" : ""}">
        <div class="turn-head"><strong>${speaker}</strong><span>✓ Confirmed</span></div>
        <p style="margin:0;font-size:13px">${text}</p>
      </div>
    </div>`;
}

function classroomVoiceView() {
  const waveHeights = [5, 18, 7, 20, 9, 22, 11, 24, 13, 26, 15, 28, 17, 6, 19, 8, 21, 10, 23, 12, 25, 14, 27, 16];
  const waveform = waveHeights
    .map((h, i) => `<span style="height:${h}px" class="${i >= 12 ? "muted" : ""}"></span>`)
    .join("");

  return `
    <main class="workspace">
      <div class="classroom-toggle">
        <button type="button" class="tab-btn" data-classroom="live">Live negotiation</button>
        <button type="button" class="tab-btn active" data-classroom="voice">Voice event review</button>
      </div>
      <div class="page-intro">
        <div class="copy">
          <p class="eyebrow">SESSION S-07  /  OPTIONAL VOICE INPUT  /  EVENT REVIEW</p>
          <h1 class="page-title">Review the event before it counts.</h1>
          <p class="page-subtitle">Voice is a capture aid—not a command. Check the meaning before updating the negotiation.</p>
        </div>
        ${pill("pending", "Pending confirmation")}
      </div>
      <div class="time-card">
        <div class="session-clock">
          ${ICON("e4001", 22, 22)}
          <div>
            <p class="clock-main">06:40 <span>/ 14:00</span></p>
            <p class="clock-sub">Paused for review · 7:20 remaining</p>
          </div>
        </div>
        <div class="phase-timeline">
          ${["Open", "Explore · now", "Package", "Close"]
            .map(
              (name, i) => `
            <div class="phase">
              <div class="phase-bar${i < 2 ? " done" : ""}"></div>
              <div class="phase-labels">
                ${i === 1 ? `<strong>${name}</strong>` : `<span>${name}</span>`}
                <span class="mono">${["0–3 min", "3–8 min", "8–12 min", "12–15 min"][i]}</span>
              </div>
            </div>`
            )
            .join("")}
        </div>
        <button type="button" class="btn">${ICON("239e1", 16, 16)} Review in progress</button>
      </div>
      ${advisoryBar("Wording may shift interpretation and strategy. Evidence and constraints stay fixed.")}
      <div class="three-col">
        ${evidencePanel()}
        <section class="col-main">
          <div class="panel-label"><span>CAPTURE → REVIEW → CONFIRM</span><span class="mono">STATE v4 UNCHANGED</span></div>
          <div class="card">
            <div class="row-actions" style="margin-bottom:16px">
              <div style="display:flex;align-items:center;gap:10px">
                ${ICON("fd089", 18, 18)}
                <h3 style="margin:0">Captured statement</h3>
              </div>
              ${pill("neutral", "Recording stopped")}
            </div>
            <div class="audio-row">
              <button type="button" class="play-btn" aria-label="Play">${ICON("ff817", 15, 15)}</button>
              <div class="waveform">${waveform}</div>
              <span class="mono" style="font-size:11px;color:var(--text-secondary)">00:04 / 00:12</span>
            </div>
            <p style="font-size:15px;margin:16px 0">“We could do $22,000 if payment is made within 15 days. Delivery would still be by 30 September, with a 12-month warranty.”</p>
            <div class="row-actions note-sm">
              <span>06:40 · Captured from Cedar Instruments · Optional voice</span>
              <button type="button" class="btn-ghost-link">Edit transcript</button>
            </div>
          </div>
          <div class="card card-accent-border">
            <div class="row-actions" style="margin-bottom:16px">
              <div>
                <h3 style="margin:0 0 3px;font-size:19px">Proposed structured event</h3>
                <p class="sub" style="margin:0">Extracted from the statement · review all six fields</p>
              </div>
              <button type="button" class="btn">${ICON("fcaa3", 16, 16)} Edit fields</button>
            </div>
            <div class="event-fields">
              ${eventField("Event type", "Conditional supplier offer", "Not an agreement")}
              ${eventField("Speaker", "Cedar Instruments", "Counterparty", false)}
              ${eventField("Total price", "$22,000 · all 24 sensors", "Within $22,800 cap")}
              ${eventField("Delivery", "By 30 September", "Matches F3", false)}
              ${eventField("Warranty", "12 months", "Matches F4")}
              ${eventField("New condition", "Payment within 15 days", "Authority not verified", false, true)}
            </div>
            <div class="alert-box" style="margin:16px 0">
              ${ICON("56b1a", 18, 18)}
              <div>
                <strong>A condition is not a commitment.</strong>
                Confirming records Cedar’s conditional offer. It does not accept the offer or authorize 15-day payment terms.
              </div>
            </div>
            <hr class="divider" />
            <div class="row-actions">
              <button type="button" class="btn" data-classroom="live">Discard capture</button>
              <button type="button" class="btn btn-primary">${ICON("379fe", 16, 16)} Confirm event</button>
            </div>
            <p class="note-sm">After confirmation: append event to the chronology, update state to v5, then refresh advisory guidance. No reply is sent.</p>
          </div>
          <div class="row-actions note-sm" style="padding:4px">
            <span>Prefer not to use voice? Enter the same event manually.</span>
            <button type="button" class="btn-ghost-link" data-classroom="live">Switch to manual input →</button>
          </div>
        </section>
        <aside class="col-side">
          <div class="panel-label"><span>BEFORE YOU CONFIRM</span><span class="mono">HUMAN CONTROL</span></div>
          <div class="card card-dark guidance-dark">
            <div class="eyebrow-row">${ICON("b9732", 17, 17)} NOTHING HAS CHANGED YET</div>
            <h2>The last confirmed offer is still $22,600.</h2>
            <p>Confirming only records what Cedar said—not your acceptance.</p>
          </div>
          <div class="card">
            <h3>Confirmation changes</h3>
            <div class="delta-grid">
              <div><p class="label">BEFORE · v4</p><p>$22,600 · standard terms</p></div>
              <div><p class="label">AFTER · v5 (proposed)</p><p>$22,000 · payment within 15 days</p></div>
            </div>
            <div style="margin-top:12px">${pill("live", "Delivery &amp; warranty unchanged")}</div>
          </div>
          <div class="card card-muted">
            <h3>Keep judgment with the negotiator</h3>
            <p>Check speaker, amount, and any “if” conditions before confirming. Voice capture can mis-hear numbers.</p>
          </div>
        </aside>
      </div>
    </main>
    ${footer("Case AQ-24 · Session S-07 · illustrative classroom data")}`;
}

function eventField(label, value, status, odd = true, warn = false) {
  return `
    <div class="field${warn ? " warn" : ""}">
      <span class="fl">${label}</span>
      <span class="fv">${value}</span>
      <span class="fs">${status}</span>
    </div>`;
}

function heatmapRows() {
  const types = ["stable", "sensitive", "changed"];
  const weights = [0.69, 0.22, 0.09];
  let seed = 24;
  const rand = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  const pick = () => {
    const r = rand();
    if (r < weights[0]) return types[0];
    if (r < weights[0] + weights[1]) return types[1];
    return types[2];
  };
  let html = "";
  for (let row = 0; row < 8; row++) {
    const start = row * 16 + 1;
    const label = `${String(start).padStart(3, "0")}–${String(start + 15).padStart(3, "0")}`;
    html += `<div class="heatmap-row"><span class="row-label">${label}</span>`;
    for (let i = 0; i < 16; i++) {
      const n = start + i;
      const id = String(n).padStart(3, "0");
      const t = n === 84 ? "changed" : pick();
      const sel = n === 84 ? " selected" : "";
      html += `<div class="heat-cell ${t}${sel}" title="V${id}">V${id.slice(-2)}</div>`;
    }
    html += "</div>";
  }
  return html;
}

function adminView() {
  const rows = [
    ["V017", "Gap made explicit", "Classroom subset", "Price → Price", "Ask about flexibility", "stable", "Stable"],
    ["V042", "Schedule first", "Classroom subset", "Price → Delivery", "Ask; verify delivery", "sensitive", "Sensitive"],
    ["V084", "Gap minimized", "Classroom subset", "Price → Price", "Concede earlier", "changed", "Changed", true],
    ["V096", "Proximity emphasis", "Research only", "Price → Price", "Concede earlier", "changed", "Changed"],
    ["V128", "Budget accommodation", "Research only", "Price → Price", "Concede earlier", "changed", "Changed"],
  ];

  return `
    <main class="workspace">
      <div class="page-intro">
        <div class="copy">
          <p class="eyebrow">RESEARCH RUN R-024  /  CASE AQ-24  /  BASELINE SNAPSHOT</p>
          <h1 class="page-title">Measure what the wording moves.</h1>
          <p class="page-subtitle">Full pre-generated perturbation set · Compare interpretations without changing the evidence.</p>
        </div>
        <div class="intro-actions">
          <button type="button" class="btn">${ICON("84412", 16, 16)} Export analysis</button>
          <button type="button" class="btn btn-primary" data-view="prep">View classroom subset</button>
        </div>
      </div>
      ${advisoryBar("128 fact-preserving variants → interpretation, priority and strategy shifts.")}
      <div class="three-col">
        <div class="col-evidence">
          ${evidencePanel("", false)}
          <div class="card">
            <h3 style="font-size:15px">Run provenance</h3>
            <p class="mono note-sm" style="line-height:1.6;margin-top:12px">
              K = 128 · pre-generated<br />
              Seed 024 · policy v2.1<br />
              Snapshot: before first offer
            </p>
            <hr class="divider" />
            ${pill("live", "128 / 128 fact checks passed")}
            <p class="note-sm">Fixed role, facts, policy and scoring rubric. Only phrasing varies between samples.</p>
          </div>
        </div>
        <section class="col-main">
          <div class="panel-label"><span>FULL PERTURBATION SET</span><span class="mono">K = 128</span></div>
          <div class="metrics-row">
            <div class="metric"><p class="num stable">88</p><h4>Stable</h4><p>Same priority &amp; strategy</p></div>
            <div class="metric"><p class="num sensitive">28</p><h4>Sensitive</h4><p>Priority or reading shifts</p></div>
            <div class="metric"><p class="num changed">12</p><h4>Recommendation changed</h4><p>Different next-move class</p></div>
          </div>
          <div class="card">
            <div class="table-tools">
              <div>
                <h3 style="margin:0 0 3px">128 wordings. One evidence set.</h3>
                <p class="sub" style="margin:0">Every cell is one scored variant, relative to the baseline.</p>
              </div>
              ${pill("live", "Analysis complete")}
            </div>
            <div class="heatmap">${heatmapRows()}</div>
            <div class="row-actions note-sm" style="margin-top:12px">
              <span>${pill("stable", "Stable")} ${pill("sensitive", "Sensitive")} ${pill("changed", "Recommendation changed")}</span>
              <span class="mono">Selected: V084</span>
            </div>
          </div>
          <div class="card">
            <div class="table-tools">
              <h3>Compare variant outcomes</h3>
              <div class="table-filters">
                <button type="button" class="btn">${ICON("798b5", 16, 16)} All outcomes</button>
                <button type="button" class="btn">${ICON("7c198", 16, 16)} Classroom first</button>
              </div>
            </div>
            <div class="results-table">
              <div class="thead">
                <span class="c-var">VARIANT</span>
                <span class="c-frame">WORDING FRAME</span>
                <span class="c-pri">PRIORITY SHIFT</span>
                <span class="c-move">NEXT MOVE</span>
                <span class="c-out">OUTCOME</span>
              </div>
              ${rows
                .map(
                  ([id, frame, tag, pri, move, ptype, plabel, sel]) => `
                <div class="trow${sel ? " selected" : ""}">
                  <span class="c-var">${id}</span>
                  <span class="c-frame"><strong>${frame}</strong><small>${tag}</small></span>
                  <span class="c-pri">${pri}</span>
                  <span class="c-move">${move}</span>
                  <span class="c-out">${pill(ptype, plabel)}</span>
                </div>`
                )
                .join("")}
            </div>
            <div class="table-foot">
              <span>1–5 of 128 · All facts preserved</span>
              <div style="display:flex;gap:8px">
                <button type="button" class="btn">Previous</button>
                <button type="button" class="btn">Next →</button>
              </div>
            </div>
          </div>
          <div class="rubric">
            <strong>Reading the result</strong>
            Stable = same interpretation, leading priority and action class. Sensitive = interpretation or priority shifts, action class stays. Changed = action class changes. These are model responses, not a forecast of human behavior.
          </div>
        </section>
        <aside class="col-side col-inspector">
          <div class="panel-label"><span>VARIANT INSPECTOR</span><span class="mono">V084</span></div>
          <div class="card">
            <div class="row-actions">
              <h3 style="margin:0;font-size:18px">Gap minimized</h3>
              <span class="mono note-sm">V084</span>
            </div>
            <div style="margin:12px 0">${pill("changed", "Recommendation changed")}</div>
            <p class="inspector-label">BASELINE</p>
            <p class="note-sm">“The quote is $24,000. Our budget is capped at $22,800; delivery is required by 30 September, with a 12-month warranty.”</p>
            <hr class="divider" />
            <p class="inspector-label" style="color:var(--changed-text)">PERTURBED WORDING</p>
            <p>“Only $1,200 separates our $22,800 budget cap from the $24,000 quote. Delivery is required by 30 September, with a 12-month warranty.”</p>
            <div style="margin-top:12px">${pill("live", "F1–F4 identical · no new facts")}</div>
          </div>
          <div class="card">
            <h3>What moved?</h3>
            <p class="inspector-label">BEFORE · EXPLORE</p>
            <p>Ask about flexibility before conceding.</p>
            <p class="inspector-label" style="margin-top:12px;color:var(--changed-text)">AFTER · EXPLORE</p>
            <p><strong>Offer a price concession earlier.</strong></p>
          </div>
          <div class="takeaway-dark">
            <p class="label">CLASSROOM TAKEAWAY</p>
            <p><strong>A smaller-sounding gap is not a better deal.</strong> “Only $1,200” adds no new evidence but can shift willingness to trade.</p>
          </div>
        </aside>
      </div>
    </main>
    ${footer("Case AQ-24 · Run R-024 · 128 / 128 validated · Baseline snapshot")}`;
}

function render() {
  const app = document.getElementById("app");
  if (!app) return;

  let body = "";
  if (state.view === "prep") body = prepView();
  else if (state.view === "admin") body = adminView();
  else body = state.classroomMode === "voice" ? classroomVoiceView() : classroomLiveView();

  app.innerHTML = appNav() + body;
  bindEvents(app);
}

function bindEvents(root) {
  root.querySelectorAll("[data-view]").forEach((el) => {
    el.addEventListener("click", () => {
      state.view = el.getAttribute("data-view");
      if (state.view === "classroom") state.classroomMode = "live";
      render();
    });
  });

  root.querySelectorAll(".workspace-nav .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.view = btn.getAttribute("data-view");
      render();
    });
  });

  root.querySelectorAll("[data-classroom]").forEach((el) => {
    el.addEventListener("click", () => {
      state.view = "classroom";
      state.classroomMode = el.getAttribute("data-classroom");
      render();
    });
  });
}

document.addEventListener("DOMContentLoaded", render);
