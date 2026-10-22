/* Optional offline source index. Excerpts are not canonical extracted facts or approval tasks. */
(function (root) {
  function classify(text) {
    if (/\b(must not|shall not|cannot|prohibited|red line|non.negotiable|not authorized|do not)\b/i.test(text)) return 'constraint';
    if (/\b(if|unless|provided that|subject to|conditional|only when)\b/i.test(text)) return 'condition';
    if (/\b(deadline|by \d|before|after|schedule|delivery|days?|weeks?|months?|january|february|march|april|may|june|july|august|september|october|november|december)\b/i.test(text)) return 'timeline';
    if (/\b(must|shall|required|requirement|limit|maximum|minimum|capped|at least|at most)\b/i.test(text)) return 'constraint';
    if (/\b(can provide|will provide|offer|commit|agree|responsib|undertake|deliver|supply)\b/i.test(text)) return 'commitment';
    if (/\b(goal|objective|prioriti|aim|seek|want|need|prefer)\w*/i.test(text)) return 'goal';
    if (/[\d$€£¥]|\b(budget|cost|capacity|staff|resources|funding)\b/i.test(text)) return 'resource';
    return 'context';
  }
  function parseSources(sources) {
    const candidates = []; let omitted = 0;
    const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('en', { granularity: 'sentence' }) : null;
    for (const source of sources) {
      const units = source.sections?.length ? source.sections.map(s=>({...s,number:null,section:s.number})) : source.pages?.length ? source.pages.map(p => ({ ...p, number: p.number })) : [{ number: null, text: source.text }];
      const seen = new Set(); let perSource = 0;
      for (const page of units) {
        const segments = segmenter ? Array.from(segmenter.segment(page.text), x => x.segment) : page.text.split(/(?<=[.!?])\s+/);
        for (const segment of segments) {
          // Preserve verbatim excerpts, including numbers, negation, and conditions.
          const parts = segment.length > 1600 ? segment.split(/\n+/) : [segment];
          for (const part of parts) {
            const quote = part.trim();
            if (quote.length < 20 || !/[a-zA-Z\u00c0-\uffff]/.test(quote) || seen.has(quote) || !source.text.includes(quote)) continue;
            seen.add(quote);
            if (perSource >= 200 || candidates.length >= 1500) { omitted++; continue; }
            const category = classify(quote);
            candidates.push({ id: `claim-${source.id}-${perSource++}`, sourceId: source.id, page: page.number, section: page.section || null, quote, text: quote, category, status: 'pending', method: 'local-rules', numbers: [...new Set((quote.match(/(?:[$€£¥]\s*)?\d[\d,.]*(?:\s*%|\s*(?:days?|weeks?|months?|years?))?/gi) || []).map(x=>x.replace(/[.,]+$/, '')))], conditional: /\b(if|unless|may|might|could|reportedly|alleg|subject to|provided that)\w*/i.test(quote) });
          }
        }
      }
    }
    return { version: 1, candidates, omitted, parsedAt: new Date().toISOString() };
  }
  const api = { classify, parseSources };
  if (typeof module !== 'undefined') module.exports = api; else root.Preparation = api;
})(typeof window !== 'undefined' ? window : globalThis);
