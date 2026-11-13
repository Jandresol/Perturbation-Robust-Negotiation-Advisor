/* Shared browser/Node domain model. No model calls or inferred utility scores. */
(function (root) {
  const stages = ['Ingest sources', 'Extract facts', 'Build baseline game', 'Validate rewordings', 'Plan and cross-score', 'Advisor review', 'Publish brief'];
  function validate(p) {
    const fail = message => { throw new Error(message); };
    if (!p || typeof p !== 'object' || Array.isArray(p)) fail('Import a package object.');
    if (p.schemaVersion !== 1) fail('schemaVersion must be 1.');
    if (typeof p.id !== 'string' || !p.id.trim() || typeof p.title !== 'string' || !p.title.trim()) fail('Package id and title are required.');
    if (!p.parties || !['us', 'opponent'].every(k => typeof p.parties[k] === 'string' && p.parties[k].trim())) fail('Provide parties.us and parties.opponent.');
    for (const key of ['sources', 'facts', 'actions', 'strategies', 'variants']) {
      if (!Array.isArray(p[key])) fail(`${key} must be an array (it may be empty).`);
      const ids = new Set();
      for (const item of p[key]) {
        if (!item || typeof item.id !== 'string' || !item.id.trim() || ids.has(item.id)) fail(`${key} needs unique, nonempty string IDs.`);
        ids.add(item.id);
      }
    }
    const has = (key, id) => p[key].some(x => x.id === id);
    const str = (x, k) => { if (typeof x[k] !== 'string' || !x[k].trim()) fail(`Missing ${k} on ${x.id}.`); };
    p.sources.forEach(x => {
      str(x, 'title'); str(x, 'text');
      if (x.sections != null && (!Array.isArray(x.sections) || x.sections.some(s=>!s||!Number.isInteger(s.number)||s.number<1||typeof s.text!=='string') || new Set(x.sections.map(s=>s.number)).size!==x.sections.length)) fail(`Invalid source sections on ${x.id}.`);
      if (x.pages != null && (!Array.isArray(x.pages) || x.pages.some(page => !page || !Number.isInteger(page.number) || page.number < 1 || typeof page.text !== 'string') || new Set(x.pages.map(page => page.number)).size !== x.pages.length)) fail(`Invalid source pages on ${x.id}.`);
    });
    p.facts.forEach(x => { str(x, 'text'); str(x, 'quote'); if (!has('sources', x.sourceId)) fail(`Unknown source on ${x.id}.`); if (!p.sources.find(s => s.id === x.sourceId).text.includes(x.quote)) fail(`Quote on ${x.id} must appear verbatim in its source.`); });
    p.actions.forEach(x => { str(x, 'label'); if (!['us', 'opponent'].includes(x.owner)) fail(`Invalid owner on ${x.id}.`); if (!has('facts', x.factId)) fail(`Unknown supporting fact on ${x.id}.`); });
    p.strategies.forEach(x => {
      str(x, 'title'); str(x, 'opening'); str(x, 'fallback');
      if (!Array.isArray(x.actionIds) || x.actionIds.some(id => !has('actions', id))) fail(`Unknown strategy actions on ${x.id}.`);
      for (const k of ['rawMean','rawWorst','baselineValue']) if (x[k] != null && !Number.isFinite(x[k])) fail(`${k} must be finite.`);
      for (const k of ['meanScore', 'worstScore']) if (x[k] != null && (!Number.isFinite(x[k]) || x[k] < 0 || x[k] > 1)) fail(`${k} must be between 0 and 1.`);
      if (x.meanScore != null && x.worstScore != null && x.worstScore > x.meanScore) fail(`Worst score exceeds mean on ${x.id}.`);
      for (const k of ['redLines', 'assumptions', 'ethicsFlags', 'branches']) if (x[k] != null && (!Array.isArray(x[k]) || x[k].some(v => typeof v !== 'string'))) fail(`${k} must be a string array.`);
    });
    p.variants.forEach(x => { str(x, 'text'); if (!['stable', 'sensitive', 'changed', 'unscored', 'rejected'].includes(x.outcome)) fail(`Invalid outcome on ${x.id}.`); if (!has('facts', x.factId)) fail(`Unknown fact on ${x.id}.`); });
    if (p.caseEdits?.redLines != null) {
      if (!Array.isArray(p.caseEdits.redLines)) fail('Red lines must be an array.');
      const ids = new Set();
      for (const r of p.caseEdits.redLines) {
        if (!r || typeof r.id !== 'string' || ids.has(r.id) || typeof r.text !== 'string' || !r.text.trim() || !['inferred','confirmed','dismissed'].includes(r.status) || !Array.isArray(r.factIds) || r.factIds.some(id=>!has('facts',id))) fail('Invalid red line or supporting fact.');
        ids.add(r.id);
      }
    }
    if (p.preparation != null) {
      const prep = p.preparation;
      if (!prep || prep.version !== 1 || !Array.isArray(prep.candidates)) fail('Invalid preparation state.');
      const ids = new Set();
      for (const c of prep.candidates) {
        if (!c || typeof c.id !== 'string' || ids.has(c.id)) fail('Preparation claim IDs must be unique.');
        ids.add(c.id);
        const source = p.sources.find(s => s.id === c.sourceId);
        if (!source || typeof c.quote !== 'string' || !c.quote.trim() || !source.text.includes(c.quote) || typeof c.text !== 'string') fail('Preparation claims need a valid source quote.');
        if (!['pending','accepted','rejected'].includes(c.status) || !['constraint','condition','timeline','commitment','goal','resource','context'].includes(c.category)) fail('Invalid claim review status or category.');
        if (c.numbers != null && (!Array.isArray(c.numbers) || c.numbers.some(x=>typeof x !== 'string'))) fail('Claim quantities must be text.');
      }
      if (prep.brief != null) {
        for (const k of ['opening','fallback']) if (typeof prep.brief[k] !== 'string') fail('Brief opening and fallback must be text.');
        for (const k of ['redLines','assumptions','branches']) if (!Array.isArray(prep.brief[k]) || prep.brief[k].some(x=>typeof x !== 'string')) fail('Brief review fields must be string arrays.');
      }
    }
    if (p.pipeline != null && (!Array.isArray(p.pipeline) || p.pipeline.length > stages.length || p.pipeline.some(x => !x || !['pending', 'running', 'complete', 'failed'].includes(x.status) || (x.detail != null && typeof x.detail !== 'string')))) fail('pipeline must contain up to seven ordered stages with valid statuses.');
    for (const k of ['role', 'objective', 'walkAway']) if (p[k] != null && typeof p[k] !== 'string') fail(`${k} must be text.`);
    return p;
  }
  function applyEvent(session, event, p) {
    if (session.mode === 'source-rehearsal' && (!['note','question','tentative','unmodeled'].includes(event.type) || event.actionIds?.length)) throw new Error('Source-only rehearsals record nonbinding observations; modeled commitments require a game.');
    if (!['offer', 'accept', 'reject', 'note', 'question', 'tentative', 'unmodeled'].includes(event.type) || !['us', 'opponent'].includes(event.speaker) || !event.text?.trim()) throw new Error('Choose an event type, speaker, and description.');
    if (!Array.isArray(event.actionIds) || new Set(event.actionIds).size !== event.actionIds.length || event.actionIds.some(id => !p.actions.some(a => a.id === id))) throw new Error('Choose valid commitment actions.');
    if (event.actionIds.some(id => session.commitments.includes(id))) throw new Error('These commitments are already binding.');
    if (['accept', 'reject'].includes(event.type)) {
      const offer = session.events.find(x => x.id === event.offerId && x.type === 'offer');
      if (!offer || offer.speaker === event.speaker || session.events.some(x => ['accept', 'reject'].includes(x.type) && x.offerId === offer.id)) throw new Error('Select an unresolved offer from the other party.');
      if (event.type === 'accept' && (event.actionIds.length !== offer.actionIds.length || offer.actionIds.some(id => !event.actionIds.includes(id)))) throw new Error('Acceptance must match the full offer.');
    }
    if (['note', 'question', 'tentative', 'unmodeled'].includes(event.type) && event.actionIds.length) throw new Error('Observations and tentative agreements cannot add commitment actions.');
    if (event.type === 'offer' && !event.actionIds.length) throw new Error('Select at least one action for the offer.');
    return { ...session, events: [...session.events, { ...event, id: `event-${session.events.length + 1}`, confirmedAt: new Date().toISOString() }], commitments: event.type === 'accept' ? [...new Set([...session.commitments, ...event.actionIds])] : [...session.commitments] };
  }
  const api = { stages, validate, applyEvent };
  if (typeof module !== 'undefined') module.exports = api;
  else root.NegotiationModel = api;
})(typeof window !== 'undefined' ? window : globalThis);
