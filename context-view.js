/* Three reading levels: case synthesis, document summary, original extracted text. */
function contextEvidence(p,ids,label='Source basis'){
 return [...new Set(ids)].filter(id=>p.facts.some(f=>f.id===id)).map(id=>`<button type="button" class="btn-ghost-link" data-inspect-fact="${esc(id)}">${esc(label)}</button>`).join(' ');
}
function situationAtGlance(p){
 const c=p.sourceAnalysis?.caseAnalysis||{},b=PrepWorkflow.draftBrief(p);
 if(c.situation){
  const x=c.situation;
  const item=(label,entry)=>entry?.text?`<div class="context-facet"><strong>${label}</strong><p>${esc(entry.text)}</p><small>${entry.status==='inferred'?'Synthesis · interpretation':entry.status==='unknown'?'Unknown · clarify':'Source-grounded account'}</small>${contextEvidence(p,entry.claim_ids||[],'Evidence')}</div>`:'';
  return `<section class="card situation-glance"><p class="eyebrow">CONTEXT</p><h2>Situation at a glance</h2>${item('Immediate situation',x.immediate)}<div class="context-facet"><strong>Who is involved</strong>${(x.actors||[]).map(e=>item('Actor / role',e)).join('')}</div>${item('Central tension',x.tension)}${item('Relevant background',x.background)}${x.uncertainty?.length?`<details><summary>Uncertainty to keep in mind</summary>${x.uncertainty.map(e=>item('To clarify',e)).join('')}</details>`:''}<details><summary>Document summaries · ${p.sources.length} sources</summary>${p.sources.map(s=>`<p><button type="button" class="btn-ghost-link" data-inspect-document="${esc(s.id)}">${esc(s.title)}</button></p>`).join('')}</details></section>`;
 }
 const ids=b.evidence.filter(f=>p.facts.some(x=>x.id===f.id)).map(f=>f.id);
 const uncertainty=(c.brief?.critical_assumptions||[]).filter(x=>x.status!=='supported').slice(0,3);
 // Use the existing cross-document synthesis, never promote an arbitrary goal-tagged fact.
 return `<section class="card situation-glance"><p class="eyebrow">CONTEXT</p><h2>Situation at a glance</h2>${c.summary?`<p>${esc(c.summary)}</p><p class="note-sm">Cross-document synthesis. Source passages below let you check its interpretation.</p><div class="context-evidence">${contextEvidence(p,ids)}</div>`:'<p>A cross-document summary is not available yet. Infer the uploaded sources to prepare the context, or inspect their text below.</p>'}<div class="situation-actors"><strong>Negotiating parties</strong><p>${esc(p.parties.us)} ↔ ${esc(p.parties.opponent)}</p><small>Roles inferred from the package or entered by your team.</small></div>${uncertainty.length?`<details><summary>Uncertainty to keep in mind</summary><ul>${uncertainty.map(x=>`<li>${esc(x.text)} ${contextEvidence(p,x.claim_ids||[],'Evidence')}</li>`).join('')}</ul><p class="note-sm">These are interpretations to verify, not established facts.</p></details>`:''}<details><summary>Document summaries · ${p.sources.length} sources</summary><div class="context-document-list">${p.sources.map(s=>`<button type="button" class="btn-ghost-link" data-inspect-document="${esc(s.id)}">${esc(s.title)}</button>`).join('')}</div></details></section>`;
}
function openSourceInspection(sourceId,factId){
 const p=state.package,source=p.sources.find(s=>s.id===sourceId);if(!source)return;
 const fact=p.facts.find(f=>f.id===factId&&f.sourceId===sourceId),a=source.analysis;
 let dialog=document.getElementById('source-inspection-dialog');
 if(!dialog){dialog=document.createElement('dialog');dialog.id='source-inspection-dialog';document.body.append(dialog);}
 const highlighted=text=>{const index=fact?.quote?text.indexOf(fact.quote):-1;return index<0?esc(text):esc(text.slice(0,index))+`<mark data-cited-passage>${esc(fact.quote)}</mark>`+esc(text.slice(index+fact.quote.length));};
 dialog.innerHTML=`<div class="row-actions"><h2>${esc(source.title)}</h2><button type="button" class="btn" id="source-inspection-close">Return to brief</button></div>${fact?`<section class="inspection-passage"><h3>Cited passage</h3><blockquote>${esc(fact.quote)}</blockquote>${fact.attribution?`<p><strong>Attribution:</strong> ${esc(fact.attribution)}</p>`:''}<p class="note-sm">${source.format==='docx'?'Section':'Page'} ${esc(fact.section||fact.page||'not supplied')}. A quoted account does not independently establish the truth of its assertions.</p></section>`:''}<section class="inspection-summary"><h3>Document summary</h3><p>${esc(a?.summary||'No document summary yet. You can read the extracted original text below while processing continues.')}</p><dl><dt>Produced by</dt><dd>${esc(a?.author||source.author||'Not identified in extracted metadata.')}</dd><dt>Date</dt><dd>${esc(a?.date||source.date||'Not identified in extracted metadata.')}</dd></dl>${a?.tags?.length?`<p>${a.tags.map(x=>badge(x)).join(' ')}</p>`:''}<p class="note-sm">This summary describes one source. The case brief synthesizes the package.</p></section><details id="inspection-full-text"><summary>Full document · extracted original text</summary>${sourceUnits(source).map(unit=>`<section><h4>${source.format==='docx'?'Section':'Page'} ${esc(unit.number)}</h4><p class="source-text">${highlighted(unit.text)}</p></section>`).join('')}<p class="note-sm">Extracted text can differ in layout from the original PDF or Word file.</p></details>`;
 document.getElementById('source-inspection-close').onclick=()=>dialog.close();
 document.getElementById('inspection-full-text').ontoggle=e=>{if(e.target.open)dialog.querySelector('[data-cited-passage]')?.scrollIntoView({block:'nearest'});};
 dialog.showModal();
}
document.addEventListener('click',event=>{
 const factLink=event.target.closest('[data-inspect-fact]');
 if(factLink){const fact=state.package?.facts.find(f=>f.id===factLink.dataset.inspectFact);if(fact)openSourceInspection(fact.sourceId,fact.id);return;}
 const sourceLink=event.target.closest('[data-inspect-document]');if(sourceLink)openSourceInspection(sourceLink.dataset.inspectDocument);
});
