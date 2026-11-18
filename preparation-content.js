/* Source-derived preparation. No planner scores, invented positions, or fixed issue taxonomy. */
function originalPreparationPassages(p){
 if(p.sourceAnalysis?.sourcePassages?.length)return p.sourceAnalysis.sourcePassages;
 return p.sources.filter(s=>s.category==='role_card').flatMap(s=>String(s.text||'').split(/\n\s*\n|\n/).filter(t=>t.trim()).map((text,i)=>({id:`passage-local-${s.id}-${i}`,text,sourceId:s.id})));
}
function preparationEntry(p,e){
 if(!e?.text)return '';
 const kind=e.status==='inferred'?'Interpretation':e.status==='unknown'?'To establish':({allegation:'Reported allegation',demand:'Stated demand',threat:'Stated threat',attributed_account:'Attributed account'})[e.evidence_kind];
 const force=({rule:'Explicit rule',approval_requirement:'Approval required',concern:'Concern',negotiating_position:'Current position'})[e.force];
 return `<div class="preparation-entry">${kind||force?`<small class="preparation-entry-kind">${esc([kind,force].filter(Boolean).join(' · '))}</small>`:''}<p>${esc(e.text)}</p>${contextEvidence(p,[...(e.claim_ids||[]),...(e.source_passage_ids||[])])}</div>`;
}
function preparationEntries(p,entries){return (entries||[]).filter(e=>e?.text).map(e=>preparationEntry(p,e)).join('');}
function issueOriginalPassages(p,issue){
 const entries=Object.values(issue).filter(Array.isArray).flat().filter(x=>x&&typeof x==='object');
 const ids=new Set(entries.flatMap(e=>e.source_passage_ids||[]));
 const facts=entries.flatMap(e=>e.claim_ids||[]).map(id=>p.facts.find(f=>f.id===id)).filter(Boolean);
 return originalPreparationPassages(p).filter(passage=>ids.has(passage.id)||facts.some(f=>f.sourceId===passage.sourceId&&passage.text.includes(f.quote)));
}
function preparationSources(p){
 const groups=new Map();for(const s of p.sources){const key=String(s.text||s.id).replace(/\s+/g,' ').trim();if(!groups.has(key))groups.set(key,[]);groups.get(key).push(s);}
 return `<p>${p.sources.length} files · ${groups.size} distinct extracted texts. Repeated or derivative accounts do not independently corroborate a statement.</p>${button('read-docs','Search all documents')}${[...groups.values()].map(copies=>{const s=copies[0],a=s.analysis;return `<details class="preparation-document-summary"><summary>${esc(s.title)}${copies.length>1?` · ${copies.length} copies`:''}${s.visibility==='private'?' · Private to our team':''}</summary><p>${esc(a?.summary||'Summary not available. Read the original extracted text.')}</p>${a?.contribution?`<p><strong>Contribution:</strong> ${esc(a.contribution)}</p>`:''}${a?.author?`<p><strong>Perspective:</strong> ${esc(a.author)}</p>`:''}${a?.date?`<p><strong>Date:</strong> ${esc(a.date)}</p>`:''}<button class="btn" type="button" data-inspect-document="${esc(s.id)}">Read original document</button></details>`;}).join('')}`;
}
function synthesizedIssue(p,issue,index){
 const useful=key=>(issue[key]||[]).filter(e=>e?.text&&!/^Not established by/.test(e.text));
 const prose=entries=>entries.map(e=>esc(e.text)).join(' ');
 const edits=typeof teamPlan==='function'?teamPlan(p).positions[issueKey(issue)]||{}:{};
 const ours=edits.ours?[{text:edits.ours}]:[...useful('our_position'),...useful('our_reasons')],theirs=edits.theirs?[{text:edits.theirs}]:[...useful('counterpart_position'),...useful('counterpart_reasons')];
 const terms=[...useful('conditions'),...useful('dependencies')],history=useful('previous_alternatives'),questions=useful('questions'),options=useful('possible_arrangements').filter(e=>e.status==='supported'||(e.status==='inferred'&&/\b(if|approval|verify|confirm|requires|provided|subject to|would need)\b/i.test(e.text)));
 const all=Object.values(issue).filter(Array.isArray).flat().filter(e=>e&&typeof e==='object');
 const ids=[...new Set(all.flatMap(e=>[...(e.claim_ids||[]),...(e.source_passage_ids||[])]))];
 return `<details class="case-agenda-item" data-issue-key="${esc(issue.id||issue.title)}"><summary><strong>${index+1}. ${esc(issue.title)}</strong></summary>${useful('decision').length?`<p>${prose(useful('decision'))}</p>`:''}${ours.length||theirs.length?`<div class="issue-position-comparison">${ours.length?`<div><h4>Our position${edits.ours?' · team edit':''}</h4><p>${prose(ours)}</p></div>`:''}${theirs.length?`<div><h4>Their position${edits.theirs?' · team interpretation':''}</h4><p>${prose(theirs)}</p></div>`:''}</div>`:''}${terms.length?`<p>${prose(terms)}</p>`:''}${history.length?`<p><strong>Already discussed:</strong> ${prose(history)}</p>`:''}${options.map(e=>typeof arrangementControl==='function'?arrangementControl(p,issue,e,(issue.possible_arrangements||[]).indexOf(e)):`<p><strong>Possibility to verify:</strong> ${esc(e.text)}</p>`).join('')}${edits.constraints?`<p><strong>Team constraint note:</strong> ${esc(edits.constraints)}</p>`:''}${questions.length?`<p><strong>Resolve:</strong> ${prose(questions)}</p>`:''}${contextEvidence(p,ids)}${typeof issueTeamControls==='function'?issueTeamControls(p,issue):''}</details>`;
}
function detailedNegotiationIssues(p){return (p.sourceAnalysis?.caseAnalysis?.negotiation_issues||[]).map((issue,i)=>synthesizedIssue(p,issue,i)).join('');}
function understandingCase(p){
 const c=p.sourceAnalysis?.caseAnalysis||{},x=c.preparation_context||{},s=c.situation||{};
 const valid=entries=>(entries||[]).filter(e=>e?.text&&!/^Not established by/.test(e.text));
 const section=(title,entries)=>valid(entries).length?`<details><summary>${title}</summary>${valid(entries).map(e=>`<p>${esc(e.text)}</p>`).join('')}${contextEvidence(p,valid(entries).flatMap(e=>[...(e.claim_ids||[]),...(e.source_passage_ids||[])]))}</details>`:'';
 const immediate=valid(x.immediate_decision),paragraph=immediate.length?immediate.map(e=>e.text).join(' '):c.summary||s.immediate?.text||'Read the sources while your preparation brief is being assembled.';
 return `<section class="card situation-glance"><h2>Understand the case</h2><p>${esc(paragraph)}</p>${contextEvidence(p,immediate.length?immediate.flatMap(e=>[...(e.claim_ids||[]),...(e.source_passage_ids||[])]):[...(c.summary_claim_ids||s.immediate?.claim_ids||[]),...(c.summary_source_passage_ids||[])])}${section('Background',x.background?.length?x.background:s.background?[s.background]:[])}${section('People, interests and power',x.people_interests_power?.length?x.people_interests_power:s.actors)}${section('Pressures and disagreements',x.pressures_disagreements?.length?x.pressures_disagreements:[s.tension,...(s.uncertainty||[])].filter(Boolean))}</section>`;
}
