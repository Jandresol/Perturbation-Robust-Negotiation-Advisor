/* Three reading levels: case synthesis, document summary, original extracted text. */
function contextEvidence(p,ids,label='Sources'){
 const facts=[...new Set(ids||[])].map(id=>p.facts.find(f=>f.id===id)||originalPreparationPassages(p).find(f=>f.id===id)).filter(Boolean);
 if(!facts.length)return '';
 const groups=new Map();
 for(const f of facts){const source=p.sources.find(s=>s.id===f.sourceId),key=String(source?.text||f.sourceId).replace(/\s+/g,' ').trim();if(!groups.has(key))groups.set(key,{source,facts:[]});groups.get(key).facts.push(f);}
 return `<details class="brief-source-links"><summary>Supporting passages (${facts.length})</summary><div>${[...groups.values()].map(({source,facts})=>`<p>${esc(source?.title||'Source')}${source?.visibility==='private'?' · Private':''}</p>${facts.map((f,i)=>`<button type="button" class="btn-ghost-link" data-inspect-fact="${esc(f.id)}">Passage ${i+1}${f.section||f.page?` · ${source?.format==='docx'?'section':'page'} ${esc(f.section||f.page)}`:''}</button>`).join(' ')}`).join('')}</div></details>`;
}
function situationAtGlance(p){
 const c=p.sourceAnalysis?.caseAnalysis||{},b=PrepWorkflow.draftBrief(p),x=c.situation;
 const paragraph=c.summary||[x?.immediate?.text,x?.tension?.text].filter(Boolean).join(' ');
 const ids=x?[...(x.immediate?.claim_ids||[]),...(x.tension?.claim_ids||[])]:b.evidence.map(f=>f.id);
 return `<section class="card situation-glance"><h2>Situation at a glance</h2><p>${esc(paragraph||'Read the uploaded sources or prepare the case summary to understand the situation.')}</p>${contextEvidence(p,ids)}${x?`<details><summary>People, background & uncertainty</summary>${x.actors?.length?`<h4>Who is involved</h4><ul>${x.actors.map(e=>`<li>${esc(e.text)}${contextEvidence(p,e.claim_ids)}</li>`).join('')}</ul>`:''}${x.background?.text?`<h4>Relevant background</h4><p>${esc(x.background.text)}</p>${contextEvidence(p,x.background.claim_ids)}`:''}${x.uncertainty?.length?`<h4>Still uncertain</h4><ul>${x.uncertainty.map(e=>`<li>${esc(e.text)}${contextEvidence(p,e.claim_ids)}</li>`).join('')}</ul>`:''}</details>`:''}<details><summary>Document summaries (${p.sources.length})</summary><div class="context-document-list">${p.sources.map(s=>`<button type="button" class="btn-ghost-link" data-inspect-document="${esc(s.id)}">${esc(s.title)}</button>`).join('')}</div></details></section>`;
}
function openSourceInspection(sourceId,factId){
 const p=state.package,source=p.sources.find(s=>s.id===sourceId);if(!source)return;
 const fact=[...p.facts,...originalPreparationPassages(p).map(x=>({...x,quote:x.text}))].find(f=>f.id===factId&&f.sourceId===sourceId),a=source.analysis;
 let dialog=document.getElementById('source-inspection-dialog');
 if(!dialog){dialog=document.createElement('dialog');dialog.id='source-inspection-dialog';document.body.append(dialog);}
 const highlighted=text=>{const index=fact?.quote?text.indexOf(fact.quote):-1;return index<0?esc(text):esc(text.slice(0,index))+`<mark data-cited-passage>${esc(fact.quote)}</mark>`+esc(text.slice(index+fact.quote.length));};
 dialog.innerHTML=`<div class="row-actions"><h2>${esc(source.title)}</h2><button type="button" class="btn" id="source-inspection-close">Return to brief</button></div>${fact?`<section class="inspection-passage"><h3>Cited passage</h3><blockquote>${esc(fact.quote)}</blockquote>${fact.attribution?`<p><strong>Attribution:</strong> ${esc(fact.attribution)}</p>`:''}<p class="note-sm">${source.format==='docx'?'Section':'Page'} ${esc(fact.section||fact.page||'not supplied')}. A quoted account does not independently establish the truth of its assertions.</p></section>`:''}${fact?.quote?`<section class="inspection-context"><h3>Surrounding text</h3><p>${esc(source.text.slice(Math.max(0,source.text.indexOf(fact.quote)-200),source.text.indexOf(fact.quote)+fact.quote.length+200))}</p></section>`:''}<section class="inspection-summary"><h3>Document summary</h3><p>${esc(a?.summary||'No document summary yet. You can read the extracted original text below while processing continues.')}</p><dl><dt>Produced by</dt><dd>${esc(a?.author||source.author||'Not identified in extracted metadata.')}</dd><dt>Date</dt><dd>${esc(a?.date||source.date||'Not identified in extracted metadata.')}</dd></dl>${a?.tags?.length?`<p>${a.tags.map(x=>badge(x)).join(' ')}</p>`:''}<p class="note-sm">This summary describes one source. The case brief synthesizes the package.</p></section><button type="button" class="btn" id="inspection-open-full">Open full document</button><details id="inspection-full-text"><summary>Full document · extracted original text</summary>${sourceUnits(source).map(unit=>`<section><h4>${source.format==='docx'?'Section':'Page'} ${esc(unit.number)}</h4><p class="source-text">${highlighted(unit.text)}</p></section>`).join('')}<p class="note-sm">Extracted text can differ in layout from the original PDF or Word file.</p></details>`;
 document.getElementById('inspection-open-full').onclick=()=>{document.getElementById('inspection-full-text').open=true;document.getElementById('inspection-full-text').scrollIntoView({block:'start'});};
 document.getElementById('source-inspection-close').onclick=()=>dialog.close();
 document.getElementById('inspection-full-text').ontoggle=e=>{if(e.target.open)dialog.querySelector('[data-cited-passage]')?.scrollIntoView({block:'nearest'});};
 dialog.showModal();
}
document.addEventListener('click',event=>{
 const factLink=event.target.closest('[data-inspect-fact]');
 if(factLink){const fact=[...(state.package?.facts||[]),...(state.package?originalPreparationPassages(state.package):[])].find(f=>f.id===factLink.dataset.inspectFact);if(fact)openSourceInspection(fact.sourceId,fact.id);return;}
 const sourceLink=event.target.closest('[data-inspect-document]');if(sourceLink)openSourceInspection(sourceLink.dataset.inspectDocument);
});
