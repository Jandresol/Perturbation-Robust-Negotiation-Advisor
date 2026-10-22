let prepTab = 'overview', docId = null, docPage = 1, docQuery = '', claimFilter = 'pending', claimSource = 'all';
const categories = ['constraint', 'condition', 'timeline', 'commitment', 'goal', 'resource', 'context'];
const ENGINE_SETTINGS = 'negotiation-engine-connections-v1';
let prepController = null, prepRunToken = 0, sourceInferenceBusy = false, workspaceInferenceProgress = {};
function ensurePreparation(p) {
  CaseModel.hydrate(p);
  if (!p.preparation) p.preparation = Preparation.parseSources(p.sources);
  // Legacy sentence suggestions are an optional source index, never a task queue.
  p.preparation.workflowVersion = 2;
  if (!p.preparation.engines) {
    try { p.preparation.engines = JSON.parse(localStorage.getItem(ENGINE_SETTINGS)) || {game:'builtin:game',perturbation:'builtin:perturbation'}; } catch { p.preparation.engines = {game:'builtin:game',perturbation:'builtin:perturbation'}; }
  }
  p.pipeline ||= [];
  if (p.sources.length && !p.pipeline[0]) p.pipeline[0] = { status: 'complete', detail: 'Source text read' };
  if (p.pipeline[1]?.detail?.includes('awaiting review')) p.pipeline[1] = { status: p.facts.length ? 'complete' : 'pending', detail: p.facts.length ? 'Source-linked facts available' : 'Waiting for package inference; no manual approval required' };
  p.pipeline=Array.from({length:p.pipeline.length},(_,i)=>p.pipeline[i]||{status:'pending'});
}
function preparationWorkspace() {
  const p=state.package;ensurePreparation(p);
  return `<section class="preparation-workspace"><ol class="preparation-steps" aria-label="Preparation progress">${['Read sources','Prepare brief','Review decisions','Start negotiation'].map((label,i)=>{const step=!p.facts.length?0:!p.sourceAnalysis?.caseAnalysis?.brief&&!p.strategies.some(s=>!s.referenceOnly)?1:state.session?3:2;return `<li class="${i===step?'current':i<step?'complete':''}" ${i===step?'aria-current="step"':''}><span>${i<step?'✓':String(i+1).padStart(2,'0')}</span><div><strong>${label}</strong><small>${i<step?'Complete':i===step?(sourceInferenceBusy?'In progress':'Current step'):'Up next'}</small></div></li>`;}).join('')}</ol><nav class="prep-nav" aria-label="Preparation workspace">${[['overview','Preparation brief'],['case','Case & constraints'],['documents','Sources'],['issues','Issues & assumptions'],['engines','Pipeline settings']].map(([key,title])=>`<button class="tab-btn ${prepTab===key?'active':''}" data-prep-tab="${key}">${title}</button>`).join('')}</nav><div class="prep-content">${prepTab==='overview'?overview(p):prepTab==='case'?caseEditor():prepTab==='documents'?documentWorkspace(p):prepTab==='issues'?issuesWorkspace(p):enginesWorkspace(p)}</div></section>`;
}
function citation(p,f){const source=p.sources.find(s=>s.id===f.sourceId);return `<button type="button" class="btn-ghost-link" data-citation-source="${esc(f.sourceId)}" data-citation-page="${f.section||f.page||1}">${esc(source?.title)}${f.section?` · section ${esc(f.section)}`:f.page&&source?.format!=='docx'?` · p. ${esc(f.page)}`:''}</button>`;}
function briefCitations(p,item){return `<div class="brief-citations">${(item?.claim_ids||[]).map(id=>{const f=p.facts.find(f=>f.id===id);return f?citation(p,f):'';}).join(' ')}</div>`;}
function adviceEvidence(p,b){
 if(!b.advice?.opening)return '';
 const entries=[['Opening',b.advice.opening],['Fallback',b.advice.fallback],['Authority',b.authority],...(b.advice.alternatives||[]).map(x=>['Alternative',x]),...(b.advice.our_constraints||[]).map(x=>['Our constraint',x]),...(b.advice.opponent_demands||[]).map(x=>['Other side’s demand',x]),...(b.advice.response_branches||[]).map(x=>['Response branch',x]),...(b.advice.critical_assumptions||[]).map(x=>['Assumption to verify',x])];
 return `<details><summary>Sources and status behind the advisory brief</summary>${entries.filter(([,x])=>x).map(([label,item])=>`<article class="advice-evidence"><strong>${esc(label)} · ${esc(item.status)}</strong><p>${esc(item.text)}</p>${briefCitations(p,item)}</article>`).join('')}</details>`;
}
function overview(p) {
  const b=PrepWorkflow.draftBrief(p),run=p.preparation.run;
  return `${sourceInferenceBusy||workspaceInferenceProgress.stopped?`<div id="workspace-inference-progress">${inferenceProgressMarkup(p.sources,workspaceInferenceProgress)}</div>`:''}${card('Workspace status', `<div class="row-actions"><span>${p.sources.length} ${p.sources.length===1?'document':'documents'} · ${p.facts.length} source-linked ${p.facts.length===1?'claim':'claims'}</span><div class="action-group">${!p.sourceAnalysis?.caseAnalysis?.brief||PrepWorkflow.isBriefStale(p)?button('infer-sources',sourceInferenceBusy?'Preparing source-linked brief…':p.sourceAnalysis?'Generate preparation brief':'Infer uploaded documents',true,sourceInferenceBusy||run?.status==='running'||!!state.session):''}${button(p.preparation.engines?.game?'start-preparation':'open-engine-settings',run?.status==='running'?'Building options…':p.preparation.engines?.game?'Build strategy options':'Connect game builder',!!p.sourceAnalysis?.caseAnalysis?.brief,run?.status==='running'||sourceInferenceBusy||(!p.facts.length&&p.preparation.engines?.game==='builtin:game'))}${run?.status==='running'?button('finalize-preparation','Stop & keep current brief'):''}</div></div><details class="processing-details"><summary>Timing & processing details</summary><p class="note-sm">Baseline target 1:30 · generation cutoff 5:00 · brief by 6:00 · team discussion through 12:00. These are targets, not measured runtime guarantees.</p><div class="pipeline-strip">${M.stages.map((title,i)=>`<div><strong>${title}</strong><small>${esc(p.pipeline[i]?.status||'pending')}${p.pipeline[i]?.detail?` · ${esc(p.pipeline[i].detail)}`:''}</small></div>`).join('')}</div>${run?.message?`<p role="status">${esc(run.message)}</p>`:''}</details>${run?.status==='running'?'<p role="status">Preparing strategy options. You can keep reviewing your brief.</p>':run?.status==='failed'?`<p class="alert-box" role="alert">${esc(run.message)}</p>`:''}`)}<div class="overview-grid"><section>${card('Your preparation brief', `<p class="eyebrow">${b.status==='plan-available'?'Plan ready for review':b.status==='advisory-brief'?'Suggested approach · review with your team':'Draft · prepare your brief'}</p>${b.briefStale?'<p class="alert-box">Case decisions changed. Generate preparation brief to refresh the advisory synthesis; manual team decisions remain saved.</p>':''}${p.preparation.modelStale&&(p.game||p.strategies.length)?'<p class="alert-box">Game recommendations are stale after a source correction. Rebuild the game before using them.</p>':''}${p.sourceAnalysis?.caseAnalysis?.summary?`<details class="case-background"><summary>Case background</summary><p>${esc(p.sourceAnalysis.caseAnalysis.summary)}</p>${p.sourceAnalysis.caseAnalysis.evidence_selection?`<p class="note-sm">Brief synthesis uses ${p.sourceAnalysis.caseAnalysis.evidence_selection.selected} decision-ranked claims out of ${p.sourceAnalysis.caseAnalysis.evidence_selection.total}. Full evidence remains available in Sources.</p>`:''}</details>`:''}${!p.sourceAnalysis?.caseAnalysis?.our_side&&(!p.parties.us||/not inferred|^our side$/i.test(p.parties.us))?`<p class="alert-box">Confirm whom we represent before using role-specific advice.</p>${button('edit-case-constraints','Confirm our side')}`:''}<h4>Our objective</h4><p>${esc(b.objective)}</p><h4>Opening</h4><p>${esc(b.opening||'Generate your brief for a proposed opening.')}</p><h4>Fallback</h4><p>${esc(b.fallback||'Set a fallback before starting the conversation.')}</p><h4>Alternatives</h4>${list(b.alternatives,'No alternatives prepared yet.')}<h4>Other side’s stated demands</h4>${list(b.opponentDemands.map(x=>x.text),'No supported demands identified yet.')}<h4>Unresolved concerns</h4>${list(b.issues.slice(0,5).map(x=>`${x.title}: ${x.detail}`),'No priority concerns identified.')}<h4>Response branches</h4>${list(b.branches,'No response branches prepared yet.')}${adviceEvidence(p,b)}<div class="row-actions">${button('print-team-brief','Print current brief')}${button('edit-team-brief','Edit team brief')}</div>`)}${card('Trades to explore',b.tradeoffs.length?`<div class="table-scroll"><table class="brief-trades"><thead><tr><th>Arrangement to explore</th><th>Potential benefit</th><th>What to verify</th></tr></thead><tbody>${b.tradeoffs.map(t=>`<tr><td>${esc(t.proposal)}${briefCitations(p,t)}</td><td>${esc(t.benefit)}</td><td>${esc(t.risk)}</td></tr>`).join('')}</tbody></table></div>`:p.actions.length?`<div class="table-scroll"><table><thead><tr><th>Commitment</th><th>Owner</th><th>Evidence</th></tr></thead><tbody>${p.actions.map(a=>{const f=p.facts.find(f=>f.id===a.factId);return `<tr><td>${esc(a.label)}</td><td>${esc(p.parties[a.owner])}</td><td>${f?citation(p,f):'Source unavailable'}</td></tr>`;}).join('')}</tbody></table></div>`:empty('The game builder has not supplied commitment options. A trade-off table will appear here when a grounded game is available.'))}${p.preparation.editBrief?briefWorkspace(p):''}</section><aside>${card('Your boundaries',`<h4>Red lines</h4>${list(b.redLines,'No confirmed red lines yet.')}<h4>Outside option</h4><p>${esc(b.outsideOption)}</p><h4>Decision authority</h4><p>${esc(b.authority?.text||'Confirm what our representative can authorize.')}</p>`)}${card('Critical evidence',b.evidence.length?b.evidence.map(f=>`<blockquote>${esc(f.quote)}<footer>${citation(p,f)}</footer></blockquote>`).join(''):empty('No readable source passages are available. Inspect the upload results.'))}${card('What to verify',list(b.assumptions,'Confirm the assumptions behind your opening.'))}${card('Start when ready',`<p>Practice from your brief with a timer and conversation log. For scored options, select a modeled strategy below.</p><div class="row-actions">${button('start-rehearsal',state.session?'Open current session':'Start source-only rehearsal',true)}</div>`)}${card('Check before starting',`<p>${b.issues.length} priority ${b.issues.length===1?'concern':'concerns'} to review.</p><div class="action-group team-focus-actions">${button('open-issues','Inspect issues')}${button('read-docs','Read & search sources')}</div>`)}</aside></div>`;
}
function issuesWorkspace(p){
  const issues=PrepWorkflow.issues(p);
  return `${card('Issues & assumptions',`<p>This view is for material source problems and model assumptions. It is optional inspection, not approval of every extracted sentence.</p>${issues.length?issues.slice(0,20).map(x=>`<article class="issue-item"><h4>${esc(x.title)}</h4><p>${esc(x.detail)}</p>${x.sourceId?citation(p,{sourceId:x.sourceId,page:x.page}):''}</article>`).join(''):empty('No specific issues have been supplied or detected. This does not establish that the model is correct.')}`)}<details><summary>Document extraction details · optional</summary>${p.sources.filter(s=>s.analysis?.limitations?.length).map(s=>`<h4>${esc(s.title)}</h4>${list(s.analysis.limitations,'')}`).join('')||empty('No extraction limitations supplied.')}</details>${card('Correct a material fact',`<p>Corrections preserve the original quotation and are recorded in the run log. If a correction affects an existing game, its recommendations become stale until rebuilt.</p><form id="fact-correction"><label>Fact<select name="factId">${p.facts.map(f=>`<option value="${esc(f.id)}">${esc(f.text.slice(0,160))}</option>`).join('')}</select></label><label>Correction<textarea name="text" rows="3" required></textarea></label><label>Reason<input name="reason" required></label><button class="btn" type="submit" ${p.facts.length?'':'disabled'}>Save correction</button></form>`)}<details><summary>Optional source index</summary><p>Searchable excerpts organized by local text rules. These are not an extraction approval queue and are not automatically passed off as canonical facts.</p><label>Search excerpts<input id="excerpt-search" type="search"></label><div id="excerpt-results"></div></details>`;
}
function sourceUnits(source) { return source.sections?.length ? source.sections : source.pages?.length ? source.pages : [{number:1,text:source.text}]; }
function documentWorkspace(p) {
  if (!p.sources.some(s=>s.id===docId)) { docId = p.sources[0]?.id; docPage = 1; }
  const source = p.sources.find(s=>s.id===docId); if (!source) return empty('Upload documents to begin.');
  const pages = sourceUnits(source);
  const results = docQuery.trim() ? p.sources.flatMap(s=>sourceUnits(s).filter(page=>page.text.toLowerCase().includes(docQuery.trim().toLowerCase())).map(page=>({source:s,page}))) : [];
  const page = pages.find(x=>x.number===docPage) || pages[0]; docPage = page.number;
  return `<div class="reader-layout"><aside class="reader-sidebar"><label>Search all documents<input id="document-search" type="search" value="${esc(docQuery)}" placeholder="Search a name, date, issue…"></label><div id="document-search-results">${searchResults(results)}</div><h4>Documents</h4>${p.sources.map(s=>`<button class="document-button ${s.id===docId?'chosen':''}" data-document="${esc(s.id)}">${esc(s.title)}<small>${sourceUnits(s).length} ${s.format==='docx'?'sections':'pages'} · ${esc(s.visibility || 'unclassified')}</small></button>`).join('')}</aside><section class="card reader-main"><div class="reader-toolbar"><h3>${esc(source.title)}</h3>${source.analysis?`<div><p>${esc(source.analysis.summary)}</p><p>${source.analysis.tags.map(tag=>badge(tag)).join(' ')}</p><details><summary>Claims and arguments</summary>${(source.analysis.claims||p.facts.filter(f=>f.sourceId===source.id)).map(f=>`<blockquote>${esc(f.text)}<footer>${esc(f.attribution)} · ${esc(f.modality)}</footer></blockquote>`).join('')}${source.analysis.arguments.map(a=>`<p><strong>${esc(a.speaker)}</strong>: ${esc(a.position)} <small>(${esc(a.kind)})</small></p>`).join('')}</details></div>`:''}<label>Visibility<select id="source-visibility"><option value="unclassified">Unclassified</option><option value="shared" ${source.visibility==='shared'?'selected':''}>Shared package</option><option value="private" ${source.visibility==='private'?'selected':''}>Our private role information</option></select></label></div><div class="row-actions">${button('prev-page','Previous section / page',false,pages.indexOf(page)===0)}<label>${source.format==='docx'?'Text section':'Page'}<select id="reader-page">${pages.map(x=>`<option value="${x.number}" ${x.number===page.number?'selected':''}>${x.number}</option>`).join('')}</select></label>${button('next-page','Next section / page',false,pages.indexOf(page)===pages.length-1)}</div><p class="note-sm">Select text in the document, then choose “Save selected passage” to save it as a source note.</p><article id="document-text" class="document-page">${highlightText(page.text,docQuery) || empty('No text layer found on this page. OCR is required.')}</article>${button('capture-passage','Save selected passage',true)}<p class="note-sm">Extracted reading order may differ for columns and tables. ${source.format==='docx'?'Word files use text sections; printed page numbers are unavailable.':'Original PDF page numbers are retained.'}</p></section></div>`;
}
function highlightText(text, query) {
  if (!query.trim()) return esc(text);
  const q=query.trim(), low=text.toLowerCase(); let start=0, out='', at;
  while ((at=low.indexOf(q.toLowerCase(),start))!==-1) { out+=esc(text.slice(start,at))+`<mark>${esc(text.slice(at,at+q.length))}</mark>`; start=at+q.length; }
  return out+esc(text.slice(start));
}
function searchResults(results) { return docQuery.trim() ? `<p class="note-sm">${results.length} matching pages</p>${results.slice(0,80).map(({source,page})=>`<button class="document-button" data-hit-source="${esc(source.id)}" data-hit-page="${page.number}">${esc(source.title)} · ${source.format==='docx'?'section':'p.'} ${page.number}<small>${esc(page.text.slice(Math.max(0,page.text.toLowerCase().indexOf(docQuery.trim().toLowerCase())-50),page.text.toLowerCase().indexOf(docQuery.trim().toLowerCase())+150))}</small></button>`).join('')}` : ''; }
function briefWorkspace(p) {
  const b=p.preparation.brief || {};
  return `<div class="overview-grid"><section>${card('Adjust team decisions', `<p>The system supplies the brief. Use this optional form to record team decisions or correct material omissions.</p><form id="team-brief-form"><label>Our objective<textarea name="objective" rows="2">${esc(p.objective || '')}</textarea></label><label>Walk-away point / outside option<textarea name="walkAway" rows="2">${esc(p.walkAway || '')}</textarea></label><label>Opening proposal<textarea name="opening" rows="3" placeholder="Team opening, if you choose to override the generated option">${esc(b.opening || '')}</textarea></label><label>Fallback<textarea name="fallback" rows="2">${esc(b.fallback || '')}</textarea></label><p>Red lines are managed in Case & constraints so their evidence and confirmation status stay consistent.</p>${button('edit-case-constraints','Edit red lines')}<label>Critical assumptions / questions (one per line)<textarea name="assumptions" rows="3">${esc((b.assumptions || []).join('\n'))}</textarea></label><label>Response branches (one per line)<textarea name="branches" rows="3" placeholder="If they reject…">${esc((b.branches || []).join('\n'))}</textarea></label><button class="btn btn-primary" type="submit">Save team brief</button></form>`)}${button('handoff','Export package')}${button('print-team-brief','Print team brief',false,!b.opening)}</section><aside>${card('Source-linked evidence',p.facts.length?p.facts.map(f=>`<blockquote>${esc(f.text)}<footer>${esc(p.sources.find(s=>s.id===f.sourceId)?.title)}${f.section?` · section ${esc(f.section)}`:f.page?` · p. ${esc(f.page)}`:''}</footer></blockquote>`).join(''):empty('Read the critical source passages while inference completes.'))}${card('Suggested review questions',list(['Which statements are attributed reports rather than established facts?','Which conditions or authorities must be confirmed?','What can our side commit to, and what requires agreement?','What is our outside option if no deal is reached?']))}</aside></div>`;
}
function referenceGameEditor(p){
 return `<details><summary>Edit reference game assumptions</summary><p>These are illustrative utility units, not inferred preferences. No real concessions are inferred. Saving clears old plans so they can be regenerated.</p><form id="reference-game-form">${p.actions.map(a=>`<fieldset><legend>Source topic action</legend><label>Label<input name="label:${esc(a.id)}" value="${esc(a.label)}" required></label><label>Owner<select name="owner:${esc(a.id)}">${['us','opponent'].map(owner=>`<option value="${owner}" ${a.owner===owner?'selected':''}>${esc(p.parties[owner])}</option>`).join('')}</select></label><label class="check"><input type="checkbox" name="forbidden" value="${esc(a.id)}" ${(p.game.forbiddenActions||[]).includes(a.id)?'checked':''}>Forbid this action</label></fieldset>`).join('')}${p.game.goals.map(g=>`<fieldset><legend>${esc(g.id)}</legend><p class="note-sm">Requires ${g.actionIds.map(id=>esc(p.actions.find(a=>a.id===id)?.label)).join(' + ')}</p><div class="form-grid"><label>Our illustrative value<input type="number" step="any" name="us:${esc(g.id)}" value="${g.usValue}" required></label><label>Opponent illustrative value<input type="number" step="any" name="opponent:${esc(g.id)}" value="${g.opponentValue}" required></label></div></fieldset>`).join('')}<button class="btn" type="submit" ${state.session?'disabled':''}>Save reference game</button></form></details>`;
}
function enginesWorkspace(p) {
  const config=p.preparation.engines || {};
  return `<div class="overview-grid"><section>${card('Local reference engines',`<p>Run the complete pipeline without extra API calls. The game models reciprocal confirmation of source topics with illustrative utilities. It does not infer real concessions or enforce all textual red lines. Edit the generated game below before interpreting scores.</p>${button('use-reference-engines','Use local reference engines',true)}${p.game?.referenceOnly?referenceGameEditor(p):''}`)}${card('Connect your teammates’ engines', `<p>The package-to-game service receives shared documents and our private role card, extracts source-linked facts once, and builds the baseline game. Rewording starts from that fixed fact set. No manual fact approvals are required.</p><form id="engine-config"><label>Game builder endpoint (optional)<input type="url" name="game" value="${esc(config.game || '')}" placeholder="http://localhost:8001/game"></label><label>Perturbation endpoint (optional)<input type="url" name="perturbation" value="${esc(config.perturbation || '')}" placeholder="http://localhost:8002/perturb"></label><button type="submit" class="btn">Save connections</button></form><p class="note-sm">Endpoints receive the package, including documents marked private. Use services authorized for your role information. Services on another port must allow this app’s origin through CORS.</p><div class="row-actions">${button('run-game','Run game builder',true,!config.game || !p.sources.length)}${button('run-perturbation','Run perturbation engine',false,!config.perturbation || !p.actions.length)}</div><div id="engine-status" role="status">${esc(p.preparation.engineStatus || '')}</div>`)}${card('Plan on the supplied game', `<p>Once the game builder provides goals and utilities, the local planner searches commitment sequences and compares them across supplied opponent readings.</p><p>Supports up to 12 actions, four offers, and two new commitments per side per offer. It models accept/reject responses to our offers, rather than a full alternating-proposer equilibrium.</p>${button('run-local-planner','Generate strategy options',true,!p.game || !p.actions.length)}<p id="planner-status" role="status">${esc(p.preparation.plannerReport?.note || '')}</p>`)}${card('File-based handoff', `<p>Without a service endpoint, export sources and available facts and import the engine’s result JSON. No game or rewording results are fabricated by this app.</p><div class="row-actions">${button('handoff','Export package')}${button('import-engine','Import engine result')}</div><input hidden type="file" id="engine-file" accept=".json,application/json">`)}</section><aside>${card('Current artifacts', `<p>${p.facts.length} source-linked facts<br>${p.actions.length} supported actions<br>${p.strategies.length} strategies<br>${p.variants.length} rewording results</p><p>Game-builder result: <code>{packageId, actions, strategies?, game?}</code><br>Perturbation result: <code>{packageId, variants}</code></p><p>All fact and action references must match this package. Failed results leave your current workspace intact.</p>`)}</aside></div>`;
}
function commitPreparation(p) { ensurePreparation(p); M.validate(p); state.package=p; save(); render(); }
function bindPreparation() {
  bindCaseEditor();
  bindWorkflowControls();
  document.querySelectorAll('[data-prep-tab]').forEach(el=>el.onclick=()=>{prepTab=el.dataset.prepTab;render();});
  document.querySelectorAll('[data-document]').forEach(el=>el.onclick=()=>{docId=el.dataset.document;docPage=1;render();});
  document.querySelectorAll('[data-hit-source]').forEach(el=>el.onclick=()=>{docId=el.dataset.hitSource;docPage=Number(el.dataset.hitPage);render();});
  document.querySelectorAll('[data-citation-source]').forEach(el=>el.onclick=()=>{docId=el.dataset.citationSource;docPage=Number(el.dataset.citationPage);docQuery='';prepTab='documents';state.view='prep';save();render();});
  document.getElementById('reader-page')?.addEventListener('change',e=>{docPage=Number(e.target.value);render();});
  document.getElementById('document-search')?.addEventListener('input',e=>{
    docQuery=e.target.value;
    const p=state.package;
    const results=docQuery.trim()?p.sources.flatMap(s=>sourceUnits(s).filter(page=>page.text.toLowerCase().includes(docQuery.trim().toLowerCase())).map(page=>({source:s,page}))):[];
    document.getElementById('document-search-results').innerHTML=searchResults(results);
    document.querySelectorAll('[data-hit-source]').forEach(el=>el.onclick=()=>{docId=el.dataset.hitSource;docPage=Number(el.dataset.hitPage);render();});
    const s=p.sources.find(s=>s.id===docId),page=sourceUnits(s).find(x=>x.number===docPage);
    document.getElementById('document-text').innerHTML=highlightText(page.text,docQuery);
  });
  document.getElementById('source-visibility')?.addEventListener('change',e=>{state.package.sources.find(s=>s.id===docId).visibility=e.target.value;save();});
  document.getElementById('team-brief-form')?.addEventListener('submit',e=>{e.preventDefault();const d=new FormData(e.target),p=state.package;const lines=k=>d.get(k).split('\n').map(x=>x.trim()).filter(Boolean);const objective=d.get('objective').trim(),walkAway=d.get('walkAway').trim();if(objective!==(p.objective||'')||walkAway!==(p.walkAway||'')){stopPreparation('Team objective or outside option changed.',false);p.preparation.modelStale=true;p.caseEdits ||= {};p.caseEdits.history ||= [];p.caseEdits.history.push({kind:'team-context',before:{objective:p.objective,walkAway:p.walkAway},after:{objective,walkAway},at:new Date().toISOString()});}p.objective=objective;p.walkAway=walkAway;p.preparation.brief={opening:d.get('opening').trim(),fallback:d.get('fallback').trim(),redLines:p.preparation.brief?.redLines||[],assumptions:lines('assumptions'),branches:lines('branches')};message='Team brief saved. Print it or continue reviewing evidence.';save();render();});
  document.getElementById('reference-game-form')?.addEventListener('submit',e=>{e.preventDefault();try{if(state.session)throw new Error('Export and clear the current session before changing game actions.');stopPreparation('Reference game edited.',false);const d=new FormData(e.target),next=structuredClone(state.package);next.referenceGameEdits={actions:Object.fromEntries(next.actions.map(a=>[a.id,{label:d.get(`label:${a.id}`).trim(),owner:d.get(`owner:${a.id}`)}])),goals:Object.fromEntries(next.game.goals.map(g=>[g.id,{usValue:Number(d.get(`us:${g.id}`)),opponentValue:Number(d.get(`opponent:${g.id}`))}])),forbiddenActions:d.getAll('forbidden')};const result=ReferenceEngines.build(next);next.actions=result.actions;next.game=result.game;next.strategies=[];next.variants=[];next.preparation.modelStale=false;next.preparation.baseline=null;state.selected=null;message='Reference assumptions saved. Run Prepare package to regenerate plans and comparisons.';commitPreparation(next);}catch(err){error(err);}});
  document.getElementById('engine-config')?.addEventListener('submit',e=>{e.preventDefault();const d=new FormData(e.target);state.package.preparation.engines={game:d.get('game').trim(),perturbation:d.get('perturbation').trim()};try{localStorage.setItem(ENGINE_SETTINGS,JSON.stringify(state.package.preparation.engines));}catch{}save();render();});
  document.getElementById('engine-file')?.addEventListener('change',async e=>{try{const file=e.target.files[0];if(!file)return;if(file.size>25*1024*1024)throw new Error('Result exceeds 25 MB.');mergeEngineResult(JSON.parse(await file.text()));}catch(err){error(err);}});
}
function mergeEngineResult(result) {
  const p=state.package;
  if (result.packageId!==p.id) throw new Error('Engine result packageId does not match this workspace.');
  if (!Array.isArray(result.actions)&&!Array.isArray(result.variants)&&!Array.isArray(result.facts)) throw new Error('Engine result must include actions or variants.');
  const next=structuredClone(p);
  for(const key of ['facts','actions','strategies','variants']) if(result[key]!=null) next[key]=result[key];
  if(result.game!=null) next.game=result.game;
  if(result.generation)next.preparation.perturbationGeneration=result.generation;
  if(result.actions && JSON.stringify(result.actions)!==JSON.stringify(p.actions) && result.strategies==null) next.strategies=[];
  M.validate(next);
  if(state.session && JSON.stringify(next.actions)!==JSON.stringify(p.actions)) throw new Error('End and export the active workspace before replacing game actions.');
  if (!next.strategies.some(s=>s.id===state.selected)) state.selected=null;
  next.preparation.engineStatus='Engine result received and references validated.';
  next.pipeline ||= [];if(result.facts)next.pipeline[1]={status:'complete',detail:'Source-linked facts extracted by inference engine'};if(result.actions)next.pipeline[2]={status:'complete',detail:'Game builder result imported'};if(result.variants)next.pipeline[3]={status:'complete',detail:'Rewording results imported; review validation in Research'};
  // Fill stage gaps explicitly for the schema.
  next.pipeline=Array.from({length:Math.max(next.pipeline.length,2)},(_,i)=>next.pipeline[i]||{status:'pending'});
  commitPreparation(next);
}
async function preparationAction(a) {
  const p=state.package; if(!p)return false;
  if(a==='read-docs'||a==='open-issues'||a==='edit-team-brief'||a==='edit-case-constraints'){prepTab=a==='read-docs'?'documents':a==='open-issues'?'issues':a==='edit-case-constraints'?'case':'overview';if(a==='edit-team-brief')p.preparation.editBrief=!p.preparation.editBrief;render();return true;}
  if(a==='prev-page'||a==='next-page'){const source=p.sources.find(s=>s.id===docId),pages=sourceUnits(source);const i=pages.findIndex(x=>x.number===docPage);docPage=pages[i+(a==='prev-page'?-1:1)]?.number||docPage;render();return true;}
  if(a==='capture-passage'){
    const selection=window.getSelection(),article=document.getElementById('document-text');
    if(!selection.rangeCount||!article.contains(selection.getRangeAt(0).commonAncestorContainer))throw new Error('Select a passage inside the document first.');
    const quote=selection.toString().trim(),source=p.sources.find(s=>s.id===docId);if(quote.length<5||!source.text.includes(quote))throw new Error('Select a continuous passage of at least five characters.');
    p.preparation.candidates.unshift({id:`manual-${crypto.randomUUID()}`,sourceId:docId,page:source.format==='docx'?null:docPage,section:source.format==='docx'?docPage:null,quote,text:quote,category:Preparation.classify(quote),status:'pending',method:'manual-selection'});message='Passage saved in the optional source index.';save();render();return true;
  }
  if(a==='use-reference-engines'){p.preparation.engines={game:'builtin:game',perturbation:'builtin:perturbation'};localStorage.setItem(ENGINE_SETTINGS,JSON.stringify(p.preparation.engines));message='Local reference engines enabled. No model calls; utilities are illustrative.';save();render();return true;}
  if(a==='open-engine-settings'){prepTab='engines';render();return true;}
  if(a==='handoff'){download('negotiation-package.json',{...p,preparation:undefined});return true;}
  if(a==='import-engine'){document.getElementById('engine-file').click();return true;}
  if(a==='print-team-brief'){printPreparationBrief(p);return true;}
  if(a==='infer-sources'){
    if(sourceInferenceBusy)return true;
    if(state.session)throw new Error('Source inference is a preparation step. Keep the current live session unchanged.');
    if(p.sourceAnalysis&&!PrepWorkflow.context(p).our_side&&!p.sources.some(s=>s.category==='role_card'||(s.visibility==='private'&&s.analysis?.represented_side))){prepTab='case';message='Confirm our side first. This avoids paying for a role-neutral brief that would need to be generated again.';render();return true;}
    const snapshot=JSON.stringify(p),controller=new AbortController();sourceInferenceBusy=true;workspaceInferenceProgress={};message='Interpreting uploaded sources… Cached analyses are reused.';render();
    const timeout=setTimeout(()=>controller.abort(),300000);
    try{
      const result=await requestSourceInference({id:p.id,sources:p.sources,context:PrepWorkflow.context(p)},controller.signal,event=>{updateInferenceProgress(workspaceInferenceProgress,event);const region=document.getElementById('workspace-inference-progress');if(region)region.innerHTML=inferenceProgressMarkup(p.sources,workspaceInferenceProgress);});
      if(state.package?.id!==p.id||JSON.stringify(state.package)!==snapshot)throw new Error('The workspace changed during inference. Retry to reuse the cached result.');
      if(!Array.isArray(result.documents)||!Array.isArray(result.facts)||!result.caseAnalysis)throw new Error('Incomplete source analysis returned.');
      const next=structuredClone(p),c=result.caseAnalysis;
      // Retain human corrections and added facts when an existing source-only case is analyzed.
      const edited=next.facts.filter(f=>f.corrected||!result.facts.some(x=>x.id===f.id));
      next.facts=[...result.facts.filter(f=>!edited.some(x=>x.id===f.id)),...edited];
      next.sources=next.sources.map(source=>{const analysis=result.documents.find(d=>d.sourceId===source.id)?.analysis;return analysis?{...source,analysis:{...analysis,claims:undefined,claim_ids:analysis.claims.map(f=>f.id)}}:source;});
      if(!next.title||next.title==='Negotiation package')next.title=c.title||next.title;
      for(const [key,value] of [['us',c.our_side],['opponent',c.opponent]])if(value&&(!next.parties[key]||next.parties[key].includes('(not inferred)')))next.parties[key]=value;
      if(!next.objective)next.objective=c.objective||'';
      if(!next.walkAway)next.walkAway=c.outside_option||'';
      next.sourceAnalysis={briefContext:JSON.stringify(PrepWorkflow.context(next)),caseAnalysis:c,caseCacheHit:result.caseCacheHit,caseAnalysisKey:result.caseAnalysisKey,cache:result.cache,documents:result.documents.map(({analysis,...metadata})=>metadata)};
      next.pipeline[1]={status:'complete',detail:'Source-linked claims, summaries, arguments and case interpretation inferred'};
      if(next.actions.length||next.strategies.length)next.preparation.modelStale=true;
      M.validate(next);message='Documents interpreted. Review the inferred case and constraints, then prepare the game.';commitPreparation(next);
    }catch(err){stopInferenceProgress(workspaceInferenceProgress);error(err.name==='AbortError'?new Error('Inference timed out. Completed document analyses are cached; retry to resume.'):err);}
    finally{clearTimeout(timeout);sourceInferenceBusy=false;render();}
    return true;
  }
  if(a==='start-preparation'){await runPreparation();return true;}
  if(a==='finalize-preparation'){stopPreparation('Generation stopped. Current source draft or baseline is retained.');return true;}
  if(a==='run-local-planner'){
    const status=document.getElementById('planner-status');if(status)status.textContent='Searching commitment sequences…';
    const executionToken=prepRunToken;
    const snapshot=JSON.stringify({actions:p.actions,game:p.game,commitments:state.session?.commitments||[]});
    const worker=new Worker('planner.js');
    const runSignal=prepController?.signal;let abortWorker=null;
    try{const result=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{worker.terminate();reject(new Error('Planning exceeded 30 seconds. Use a smaller game or external planner.'));},30000);abortWorker=()=>{clearTimeout(timeout);worker.terminate();reject(new Error('Preparation stopped.'));};runSignal?.addEventListener('abort',abortWorker,{once:true});worker.onmessage=e=>{clearTimeout(timeout);e.data.ok?resolve(e.data.result):reject(new Error(e.data.error));};worker.onerror=()=>{clearTimeout(timeout);reject(new Error('The planner worker could not run.'));};worker.postMessage({package:p,commitments:state.session?.commitments||[]});});
      if(executionToken!==prepRunToken||state.package.id!==p.id||snapshot!==JSON.stringify({actions:state.package.actions,game:state.package.game,commitments:state.session?.commitments||[]}))throw new Error('Game or session changed while planning. Run the planner again.');
      if(p.game.referenceOnly)for(const s of result.strategies){s.title='Reference simulation: '+s.title;s.referenceOnly=true;s.redLines=PrepWorkflow.draftBrief(p).redLines;s.assumptions=[...p.game.assumptions,...s.assumptions];s.ethicsFlags.unshift('Reference simulation only: numerical values are illustrative, not sourced human utilities.');}p.strategies=[...p.strategies.filter(s=>s.method!=='local-exact'),...result.strategies];p.preparation.plannerReport=result.report;
      p.pipeline[4]={status:'complete',detail:`${result.strategies.length} local options; advisor review pending`};p.pipeline=Array.from({length:p.pipeline.length},(_,i)=>p.pipeline[i]||{status:'pending'});
      message=result.strategies.length?'Strategy options generated. Review the planner results below.':'No improving sequence was found under the supplied utility model and offer limits.';commitPreparation(p);
    }finally{if(abortWorker)runSignal?.removeEventListener('abort',abortWorker);worker.terminate();}return true;
  }
  if(a==='run-game'||a==='run-perturbation'){
    const endpoint=p.preparation.engines?.[a==='run-game'?'game':'perturbation'];if(!endpoint)throw new Error('Save an engine endpoint first.');
    p.preparation.engineStatus='Running…';save();const status=document.getElementById('engine-status');if(status)status.textContent='Running…';
    try{if(endpoint==='builtin:game'||endpoint==='builtin:perturbation'){mergeEngineResult(endpoint==='builtin:game'?ReferenceEngines.build(p):ReferenceEngines.perturb(p));return true;}const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({schemaVersion:1,packageId:p.id,package:{...p,preparation:undefined}}),signal:AbortSignal.timeout(120000)});if(!response.ok)throw new Error(`Engine returned HTTP ${response.status}.`);const result=await response.json();if(state.package.id!==p.id)throw new Error('Workspace changed while the engine was running.');mergeEngineResult(result);}catch(err){p.preparation.engineStatus=`Could not complete: ${err.message}`;save();if(state.package.id===p.id)render();throw err;}return true;
  }
  return false;
}

function bindWorkflowControls(){
  document.getElementById('excerpt-search')?.addEventListener('input',e=>{
    const q=e.target.value.toLowerCase().trim(),p=state.package;
    const matches=q?p.preparation.candidates.filter(c=>c.text.toLowerCase().includes(q)).slice(0,15):[];
    document.getElementById('excerpt-results').innerHTML=matches.map(c=>`<blockquote>${esc(c.text)}<footer>${citation(p,c)}</footer></blockquote>`).join('');
    document.querySelectorAll('[data-citation-source]').forEach(el=>el.onclick=()=>{docId=el.dataset.citationSource;docPage=Number(el.dataset.citationPage);docQuery='';prepTab='documents';state.view='prep';save();render();});
  });
  document.getElementById('fact-correction')?.addEventListener('submit',e=>{
    e.preventDefault();try{
      const data=new FormData(e.target),p=state.package,f=p.facts.find(f=>f.id===data.get('factId'));if(!f)throw new Error('Select an extracted fact.');
      const text=data.get('text').trim(),reason=data.get('reason').trim();if(!text||!reason)throw new Error('Provide a correction and reason.');
      stopPreparation('Preparation stopped because the source interpretation was corrected.',false);
      p.preparation.corrections ||= [];p.preparation.corrections.push({factId:f.id,before:f.text,after:text,reason,at:new Date().toISOString()});f.text=text;f.corrected=true;
      p.preparation.modelStale=true;
      message='Correction logged. Existing recommendations are marked stale; rebuild the game before relying on them.';
      save();render();
    }catch(err){error(err);}
  });
}
function printPreparationBrief(p){
  const b=PrepWorkflow.draftBrief(p),region=document.createElement('section');region.id='print-brief';
  region.innerHTML=`<h1>${esc(p.title)}</h1><p>${b.status==='source-draft'?'Source draft · generate preparation brief':b.status==='advisory-brief'?'Source-linked advisory brief · proposed advice requires team judgment':'Preparation plan · estimates require team judgment'}</p><h3>Objective</h3><p>${esc(b.objective)}</p><h3>Outside option</h3><p>${esc(b.outsideOption)}</p><h3>Decision authority</h3><p>${esc(b.authority?.text||'Confirm authority before committing.')}</p><h3>Other side’s demands</h3>${list(b.opponentDemands.map(x=>x.text),'Not identified.')}<h3>Opening</h3><p>${esc(b.opening||'Not yet supplied by the game and planner.')}</p><h3>Fallback</h3><p>${esc(b.fallback||'Return to source evidence and team constraints.')}</p><h3>Red lines</h3>${list(b.redLines,'No confirmed red lines supplied.')}<h3>Alternatives</h3>${list(b.alternatives,'No alternatives supplied.')}<h3>Potential trades · advisory</h3>${list(b.tradeoffs.map(t=>`${t.proposal} Benefit: ${t.benefit} Verify: ${t.risk}`),'No supported trades supplied.')}<h3>Response branches</h3>${list(b.branches,'None of these branches fit: pause and return to sources and red lines.')}<h3>High-impact assumptions</h3>${list(b.assumptions,'No model assumptions supplied.')}<h3>Critical sources</h3>${b.evidence.map(f=>`<blockquote>${esc(f.quote)}<footer>${esc(p.sources.find(s=>s.id===f.sourceId)?.title)}${f.section?` · section ${esc(f.section)}`:f.page?` · p. ${esc(f.page)}`:''}</footer></blockquote>`).join('')}<h3>Unresolved concerns</h3>${list(b.issues.slice(0,5).map(x=>`${x.title}: ${x.detail}`),'No specific concerns supplied.')}`;
  document.body.append(region);window.print();region.remove();
}
function stopPreparation(reason,redraw=true){
  prepRunToken++;prepController?.abort();prepController=null;
  const run=state.package?.preparation?.run;
  if(run?.status==='running'){run.status='finalized';run.finishedAt=Date.now();run.message=reason;state.package.pipeline=state.package.pipeline.map(stage=>stage.status==='running'?{status:'pending',detail:'Stopped; previous available artifacts retained'}:stage);state.package.pipeline[6]={status:'complete',detail:'Current fallback brief assembled'};state.package.pipeline=Array.from({length:7},(_,i)=>state.package.pipeline[i]||{status:'pending'});save();}
  if(redraw)render();
}
async function runPreparation(){
  const p=state.package;if(!p)return;ensurePreparation(p);
  if(p.preparation.run?.status==='running')return;
  const config=p.preparation.engines||{};
  if(!config.game){
    p.preparation.run={status:'waiting',startedAt:Date.now(),message:'Document interpretation is available when analyzed. The peer game builder is not connected. Configure the service in Pipeline settings; no sentence approvals or manual fact entry are required.'};save();render();return;
  }
  const id=p.id,token=++prepRunToken,controller=new AbortController();prepController=controller;
  const active=()=>prepRunToken===token&&state.package?.id===id&&state.package.preparation.run?.status==='running';
  p.preparation.run={status:'running',startedAt:Date.now(),message:'Extracting source-linked facts and building the baseline from the package…',stages:[]};
  p.pipeline[1]={status:'running',detail:'Automatic package inference'};p.pipeline[2]={status:'running',detail:'Building baseline game'};save();render();
  const cutoff=setTimeout(()=>{if(active())stopPreparation('Five-minute generation cutoff reached. Current baseline or source draft retained.');},PrepWorkflow.STOP_GENERATION_MS);
  const record=(stage,status,detail)=>{
    if(!active())return;
    const current=state.package;current.pipeline[stage]={status,detail};current.preparation.run.stages.push({stage,status,at:Date.now(),detail});current.preparation.run.message=detail;save();render();
  };
  async function call(endpoint){
    const snapshot=structuredClone(state.package);if(endpoint==='builtin:game')return ReferenceEngines.build(snapshot);if(endpoint==='builtin:perturbation')return ReferenceEngines.perturb(snapshot);const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({schemaVersion:1,packageId:id,package:{...snapshot,preparation:undefined},task:'prepare',factSetFrozen:!!snapshot.preparation.baseline}),signal:controller.signal});
    if(!response.ok)throw new Error(`Service returned HTTP ${response.status}.`);
    const result=await response.json();if(!active())return null;if(result.packageId!==id)throw new Error('Service result belongs to a different package.');return result;
  }
  try{
    const baseline=await call(config.game);if(!baseline)return;
    mergeEngineResult(baseline);
    if(!active())return;
    if(!Array.isArray(baseline.actions)||(!baseline.game&&!baseline.strategies?.length))throw new Error('Inference returned no complete baseline game or plan. Partial sources/facts remain available.');
    state.package.preparation.modelStale=false;
    if(state.package.game?.goals?.length&&state.package.actions.length){record(4,'running','Planning baseline commitment options…');await preparationAction('run-local-planner');}
    if(!active())return;
    state.package.preparation.baseline={facts:structuredClone(state.package.facts),actions:structuredClone(state.package.actions),game:structuredClone(state.package.game||null),strategies:structuredClone(state.package.strategies),savedAt:Date.now()};
    record(2,'complete','Baseline stored. Available while additional readings run.');
    if(config.perturbation&&state.package.facts.length&&PrepWorkflow.canGenerate(state.package.preparation.run)){
      record(3,'running','Running fact rewordings against the fixed extracted fact set…');
      try{
        const result=await call(config.perturbation);if(!result)return;
        // Keep baseline actions, facts, and strategy menu intact unless all release gates are explicit.
        mergeEngineResult({packageId:id,variants:result.variants||[],generation:result.generation});
        const gates=result.release;
        if(gates?.sourceSupport===true&&gates.feasibility===true&&gates.ethicsReviewed===true&&gates.freshRescored===true){
          const next=structuredClone(state.package);
          if(result.strategies)next.strategies=result.strategies;
          if(result.game)next.game=result.game;
          M.validate(next);commitPreparation(next);
        }else record(3,'complete','Rewording results available for inspection. Baseline retained; validated release gates not supplied.');
      }catch(err){if(!active())return;record(3,'failed',`Additional readings failed; baseline retained. ${err.message}`);}
    }
    if(!active())return;
    const current=state.package;
    current.pipeline[6]={status:'complete',detail:current.strategies.length?'Brief assembled from available baseline and released results':'Source draft assembled; modeled options incomplete'};
    current.pipeline=Array.from({length:7},(_,i)=>current.pipeline[i]||{status:'pending'});
    current.preparation.run.status='complete';current.preparation.run.finishedAt=Date.now();current.preparation.run.message='Brief ready for team discussion. Inspect critical evidence and unresolved assumptions; choose your opening and fallback.';save();render();
  }catch(err){
    if(active()){
      const current=state.package;current.pipeline[2]={status:'failed',detail:err.message};current.preparation.run.status='failed';current.preparation.run.message=`Baseline inference did not finish. Source draft is still available. ${err.message}`;save();render();
    }
  }finally{clearTimeout(cutoff);if(prepController===controller)prepController=null;}
}
