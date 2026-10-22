/* Dataset-driven workspace. Imported results are supplied by the external pipeline. */
const M = window.NegotiationModel;
const STORE = 'negotiation-workspace-v1';
let state = { package: null, selected: null, view: 'prep', session: null };
let analysisPage = 0;
let pending = null, draft = null, filter = 'all', search = '', inspected = null, message = '', storageWarning = '';
try {
  const saved = JSON.parse(localStorage.getItem(STORE));
  if (saved?.package) {
    M.validate(saved.package);
    if (saved.package.preparation?.run?.status === 'running') { saved.package.preparation.run.status = 'interrupted'; saved.package.preparation.run.message = 'Preparation was interrupted by reload. Available baseline and source draft were preserved; restart preparation to continue.'; }
    const session = saved.session;
    if (session) {
      let replay = { ...session, events: [], commitments: [] };
      for (const event of session.events) replay = M.applyEvent(replay, event, saved.package);
      saved.session = replay;
      saved.session.running = false;
    }
    state = { ...state, ...saved, view: ['prep', 'classroom', 'admin'].includes(saved.view) ? saved.view : 'prep' };
  }
} catch { storageWarning = 'Saved workspace could not be restored. Import a package to continue.'; }
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const button = (action, text, primary = false, disabled = false) => `<button type="button" class="btn ${primary ? 'btn-primary' : ''}" data-action="${action}" ${disabled ? 'disabled' : ''}>${text}</button>`;
const badge = (text, type = 'neutral') => `<span class="pill pill-${type}">${esc(text)}</span>`;
const card = (title, content, extra = '') => `<section class="card ${extra}"><h3>${title}</h3>${content}</section>`;
const empty = text => `<p class="empty">${esc(text)}</p>`;
const list = (items, fallback) => items?.length ? `<ul>${items.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : empty(fallback);
const selected = () => state.package?.strategies.find(x => x.id === state.selected);
const fmt = seconds => `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
function save() { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch { storageWarning = 'Browser storage is unavailable or full. Export your session before leaving.'; } }
function download(name, data, type = 'application/json') {
  const url = URL.createObjectURL(new Blob([type === 'application/json' ? JSON.stringify(data, null, 2) : data], { type }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function evidence() {
  const p = state.package;
  return `<aside class="col-evidence"><div class="panel-label">PACKAGE & EVIDENCE</div>${card('Your role', `<p>${esc(p.role || p.parties.us)}</p><p class="sub">Opposite ${esc(p.parties.opponent)}</p><p>${esc(p.objective || 'Review the package and define your objective with the team.')}</p>`)}${card('Evidence ledger', p.facts.length ? p.facts.map((f,i) => `<details class="evidence-entry"><summary><span class="evidence-label">F${i+1} · ${esc((f.category||'claim').replace(/^./,c=>c.toUpperCase()))}</span><span class="evidence-description">${esc(f.text)}</span></summary><blockquote>${esc(f.quote)}</blockquote>${citation(p,f)}<p class="note-sm">${f.attribution?`Attributed to ${esc(f.attribution)}. `:''}Quote matched in supplied source; meaning requires review.</p><details class="technical-reference"><summary>Technical reference</summary><code>${esc(f.id)}</code></details></details>`).join('') : empty('No extracted facts supplied.'))}${card('Source documents', p.sources.length ? p.sources.map(s => `<details><summary>${esc(s.title)}</summary>${s.pages?.length ? s.pages.map(page => `<details><summary>Page ${esc(page.number)}</summary><p class="source-text">${esc(page.text || 'No readable text. OCR may be needed.')}</p></details>`).join('') : `<p class="source-text">${esc(s.text)}</p>`}</details>`).join('') : empty('No sources supplied.'))}${card('Walk-away point', `<p>${esc(p.walkAway || 'Not supplied. Agree on an outside option before negotiating.')}</p>`, 'card-muted')}</aside>`;
}
function brief(s) {
  return `<p class="eyebrow">SELECTED STRATEGY</p><h2>${esc(s.title)}</h2><h4>Opening</h4><p>${esc(s.opening)}</p><h4>Fallback</h4><p>${esc(s.fallback)}</p><h4>Red lines</h4>${list(s.redLines, 'No red lines supplied. Review with the team.')}<h4>Critical assumptions</h4>${list(s.assumptions, 'No assumptions supplied.')}<h4>Response branches</h4>${list(s.branches, 'No contingent tree supplied.')}<h4>Ethics review</h4>${list(s.ethicsFlags, 'No ethics flags supplied; this does not establish review completion.')}`;
}
function rehearsalBrief(){
  const b=PrepWorkflow.draftBrief(state.package);
  return `<h4>Objective</h4><p>${esc(b.objective)}</p><h4>Opening</h4><p>${esc(b.opening||'Team decides; no modeled opening is available.')}</p><h4>Fallback / outside option</h4><p>${esc(b.fallback||b.outsideOption)}</p><h4>Red lines</h4>${list(b.redLines,'No red lines supplied.')}<h4>Questions to clarify</h4>${list(b.assumptions.length?b.assumptions:b.issues.slice(0,3).map(x=>x.detail),'Confirm the other side’s priorities, constraints, and authority before making commitments.')}`;
}
function guidance() {
  const p=state.package,session=state.session,s=session?p.strategies.find(x=>x.id===session.strategyId):selected();
  const b=PrepWorkflow.draftBrief({...p,preparation:{...p.preparation,chosenStrategyId:s?.id||p.preparation?.chosenStrategyId}});
  const events=session?.events||[],latest=events.at(-1);
  const openOffer=session?unresolved().filter(e=>e.speaker==='opponent').at(-1):null;
  const objective=p.objective||p.sourceAnalysis?.caseAnalysis?.objective;
  let next=b.opening||`Ask ${p.parties.opponent} what outcome they need and who can authorize the terms.`;
  if(latest)next='Check your understanding of the last exchange, then use the response branches below to choose your next move.';
  if(openOffer)next='Clarify the conditions of the outstanding offer. Compare the full package with your red lines and outside option before responding.';
  if(latest?.type==='reject')next='Ask which term blocks agreement. Explore a prepared alternative without giving up a red line.';
  if(latest?.type==='accept')next='Restate the accepted terms and check responsibilities, timing, and any remaining conditions before proposing more.';
  if(events.some(e=>e.type==='unmodeled'))next='A new issue falls outside the prepared model. Clarify it and check the sources and team authority before making a commitment.';
  const liveAdvice=LiveStrategy.current;
  if(liveAdvice)next=liveAdvice.next;
  if(session?.ended)next='Compare the confirmed conversation with your objective, accepted commitments, and unresolved issues.';
  return `<aside class="col-side strategy-guidance" aria-label="Strategy guidance"><div class="panel-label">STRATEGY GUIDANCE</div>${card(session?.ended?'Review the outcome':'Your next move',`<h4>Your objective</h4><p>${esc(objective||'Your objective is not defined yet. Confirm the outcome your team wants in Case & constraints.')}</p><h4>${events.length?'Suggested next step':'Start with this approach'}</h4><p>${esc(next)}</p><p class="note-sm" role="status">${LiveStrategy.status==='updating'?'Updating guidance in the background… You can keep recording.':LiveStrategy.status==='limited'?'Update unavailable; your prepared guidance remains available.':liveAdvice?`Updated through turn ${liveAdvice.events}.`:'Use your prepared brief to guide the conversation.'} The team chooses the response.</p>`,'card-dark')}${card('Your strategy',`${s&&!s.referenceOnly?`<p class="eyebrow">${esc(s.title)}</p>`:''}<h4>Opening approach</h4><p>${esc(b.opening||'State your objective and ask about their priorities before proposing terms.')}</p><h4>If the opening stalls</h4><p>${esc(b.fallback||'Ask what is blocking progress and explore the alternatives below.')}</p>${b.alternatives.length?`<h4>Alternatives to explore</h4>${list(b.alternatives)}`:''}${b.briefStale||p.preparation?.modelStale?'<p class="alert-box">The case has changed since preparation. Review this advice against your current sources and constraints.</p>':''}${s?.referenceOnly?'<p class="note-sm">Local simulation scores are illustrative. Use the document-grounded approach and your team’s decisions here.</p>':''}`)}${card('Protect your boundaries',`<h4>Red lines</h4>${list(b.redLines,'Confirm your non-negotiable limits with the team.')}<h4>Outside option</h4><p>${esc(b.outsideOption)}</p>${b.authority?.text?`<h4>Decision authority</h4><p>${esc(b.authority.text)}</p>`:''}`)}${liveAdvice?.asks?.length?card('Make the position concrete',`<p class="note-sm">Suggested questions based on relevant source claims; confirm the facts with the other side.</p>${liveAdvice.asks.map(a=>{const f=p.facts.find(f=>f.id===a.factId);return `<p>${esc(a.text)}</p>${f?citation(p,f):''}`;}).join('')}`):''}${liveAdvice?.options?.length?card('Updated strategy options',liveAdvice.options.slice(0,2).map(o=>`<p>${esc(o.opening)}</p>`).join('')):''}${card('How to respond',list(b.branches,'Ask about priorities, test a conditional trade, and summarize what remains unresolved.'))}${b.assumptions.length?card('Check before committing',list(b.assumptions)):''}<p class="note-sm">${esc(liveAdvice?.planningStatus||'Updates use confirmed exchanges and saved sources.')} Spoken notes do not change commitments until confirmed.</p></aside>`;
}
function strategyView() {
  const p=state.package;
  return `<section class="card"><h3>Choose an opening and fallback</h3><p class="sub">Compare the available options and their assumptions. Scores are estimates on supplied games, not measured human outcomes.</p><div class="strategy-menu">${p.strategies.slice(0,5).map(s=>`<article class="strategy ${state.selected===s.id?'chosen':''}"><h3>${esc(s.title)}</h3><p>${esc(s.opening)}</p><p class="note-sm">Fallback: ${esc(s.fallback)}</p><details><summary>Assumptions, evidence, and estimated values</summary>${list(s.assumptions,'No assumptions supplied.')}<p>Mean score: ${s.meanScore==null?'unavailable':esc(s.meanScore.toFixed(2))} · worst: ${s.worstScore==null?'unavailable':esc(s.worstScore.toFixed(2))}</p>${list(s.ethicsFlags,'No ethics review supplied.')}</details><button class="btn ${state.selected===s.id?'btn-primary':''}" data-select="${esc(s.id)}">${state.selected===s.id?'Selected':'Select strategy'}</button></article>`).join('')||empty('No strategy menu available yet.')}</div><div class="row-actions">${button('print','Print selected plan',false,!selected())}${button('start',state.session?'Open negotiation':'Start negotiation',true,!state.session&&(!selected()||p.preparation?.modelStale))}</div></section>`;
}
function prep() {
  return preparationWorkspace() + (state.package.strategies.length || state.package.actions.length ? `<details class="strategy-results" ${state.selected || state.package.strategies.some(s=>s.method==='local-exact') ? 'open' : ''}><summary>Strategy options · ${state.package.strategies.length} ${state.package.strategies.length===1?'option':'options'}</summary>${strategyView()}</details>` : '');
}
function unresolved() { return state.session.events.filter(e => e.type === 'offer' && !state.session.events.some(x => ['accept', 'reject'].includes(x.type) && x.offerId === e.id)); }
function form(){
 const p=state.package,rehearsal=state.session?.mode==='source-rehearsal',d=draft||{type:'note',speaker:'us',text:'',actionIds:[],offerId:''};
 const labels={offer:'New offer',accept:'Acceptance',reject:'Rejection',question:'Question',tentative:'Tentative agreement',unmodeled:'New issue / not modeled',note:'Conversation note'};
 return `<form id="event-form"><div id="voice-capture">${VoiceCapture.markup()}</div><h4>2. Check the exchange</h4><label>Transcript or typed notes<textarea name="text" required maxlength="5000" rows="4" placeholder="Record voice above, or type what was said. Preserve amounts, conditions, and uncertainty.">${esc(d.text)}</textarea></label><div class="form-grid"><label>Who spoke?<select name="speaker">${['us','opponent'].map(k=>`<option value="${k}" ${d.speaker===k?'selected':''}>${esc(p.parties[k])}</option>`).join('')}</select></label><label>What happened?<select name="type">${(rehearsal?['note','question','tentative','unmodeled']:['note','question','offer','accept','reject','tentative','unmodeled']).map(t=>`<option value="${t}" ${d.type===t?'selected':''}>${labels[t]}</option>`).join('')}</select></label></div>${!rehearsal&&['accept','reject'].includes(d.type)?`<label>Which offer are they responding to?<select name="offerId"><option value="">Choose an unresolved offer</option>${unresolved().filter(e=>e.speaker!==d.speaker).map(e=>`<option value="${esc(e.id)}" ${d.offerId===e.id?'selected':''}>${esc(e.text)}</option>`).join('')}</select></label><p class="note-sm">Only explicit acceptance of the full referenced offer adds commitments.</p>`:''}${!rehearsal&&d.type==='offer'?`<fieldset><legend>Offer terms in the prepared model</legend><p class="note-sm">Select only terms actually proposed. If none fit, use New issue / not modeled.</p>${p.actions.filter(a=>!state.session.commitments.includes(a.id)).map(a=>`<label class="check"><input type="checkbox" name="actionIds" value="${esc(a.id)}" ${d.actionIds.includes(a.id)?'checked':''}>${esc(p.parties[a.owner])}: ${esc(a.label)}</label>`).join('')||empty('No uncommitted model actions are available.')}</fieldset>`:''}<p class="note-sm">Recording and transcription never create commitments. Review the text and confirm the structured event yourself.</p><button class="btn btn-primary" type="submit">Review event</button></form>`;
}
function live() {
  const s = state.session;
  if (!s) return card('Prepare first', `<p>Select a strategy in preparation before starting a negotiation.</p>${button('prep', 'Go to preparation', true)}`);
  return `<div class="time-card"><div class="session-clock"><div><p class="clock-main" id="clock">${fmt(s.elapsed)} <span>/ ${fmt(s.duration)}</span></p><p class="clock-sub" id="clock-status">${s.ended ? 'Session ended' : s.running ? 'Running' : 'Paused'} · ${Math.max(0, Math.ceil((s.duration - s.elapsed) / 60))} min remaining</p></div></div>${button('pause', s.running ? 'Pause session' : 'Resume timer', false, s.ended)}${button('end', 'End & debrief', false, s.ended)}${button('export', 'Export session')}</div><div class="three-col">${evidence()}<div class="col-main">${s.mode==='source-rehearsal'?card('Source-only rehearsal','<p>Use your source-grounded brief and record the conversation. Offers and agreements are notes only: no game, numerical recommendations, or binding commitment encoding is available.</p>'):''}${s.ended ? card('Session debrief', `<p>${s.events.length} confirmed events · ${s.commitments.length} binding commitments · ${fmt(s.elapsed)} elapsed.</p><p>Utility, regret, and agreement quality require planner or evaluator results.</p>${button('export', 'Download event log', true)}`) : ''}${card('Confirmed conversation', s.events.length ? s.events.map((e,i) => `<article class="turn-bubble"><div class="turn-head"><strong>${esc(state.package.parties[e.speaker])} · ${esc(e.type)}</strong><span>Turn ${i+1} · Confirmed</span></div><p>${esc(e.text)}</p>${e.capture?.audioId?`<audio controls data-voice-clip="${esc(e.capture.audioId)}"></audio><p><a data-audio-download="${esc(e.capture.audioId)}" class="btn-ghost-link">Download recording</a></p>`:''}<small>${e.actionIds.map(id => esc(state.package.actions.find(a => a.id === id)?.label)).join(' · ')}</small></article>`).join('') : empty('Start with Record voice below, or type a note. Nothing is logged until you review and confirm it.'))}${s.events.some(e=>e.type==='unmodeled')?card('Outside the prepared model','<p class="alert-box">A new issue has been recorded. Prepared scores and recommendations omit it. Return to sources and team constraints; accepted commitments remain binding.</p>'):''}${card('Binding commitments', s.commitments.length ? list(s.commitments.map(id => state.package.actions.find(a => a.id === id).label)) : empty('No accepted commitments.'))}${!s.ended ? card(pending ? 'Proposed event' : 'Record an exchange', pending ? `<p>${badge(pending.type)} ${esc(state.package.parties[pending.speaker])}</p><p>${esc(pending.text)}</p>${pending.capture?.audioId?`<audio controls data-voice-clip="${esc(pending.capture.audioId)}"></audio><details><summary>Original voice transcript</summary><p>${esc(pending.capture.rawTranscript||'No browser transcript; review the recording and typed notes.')}</p></details>`:''}${list(pending.actionIds.map(id => state.package.actions.find(a => a.id === id).label), 'No actions added by this event.')}<p class="alert-box">${pending.type === 'accept' ? 'Confirming acceptance adds every action in the referenced offer to binding commitments.' : 'This event will be logged. Binding commitments remain unchanged.'}</p><div class="row-actions">${button('edit', 'Back to edit')}${button('confirm', 'Confirm event', true)}</div>` : form()) : ''}</div>${guidance()}</div>`;
}
function isControl(v){return ['formatting-control','same-text-control'].includes(v.method);}
function comparisonComplete(v){return v.comparisonCompleted===true||(typeof v.gameUnchanged==='boolean'&&typeof v.planUnchanged==='boolean')||(!isControl(v)&&['stable','sensitive','changed'].includes(v.outcome));}
function readingLabel(v){return isControl(v)?comparisonComplete(v)?(v.gameUnchanged===false||v.planUnchanged===false?'Control changed':'Control unchanged'):'Control pending':v.outcome;}
function readingClass(v){return isControl(v)?'control':v.outcome;}
function readingBadge(v){return badge(readingLabel(v),isControl(v)?'control':['stable','sensitive','changed'].includes(v.outcome)?v.outcome:'neutral');}
function filteredReadings(){return state.package.variants.filter(v=>(filter==='all'||filter==='controls'&&isControl(v)||filter==='unscored'&&v.outcome==='unscored'&&!comparisonComplete(v)||!isControl(v)&&v.outcome===filter&&filter!=='unscored')&&`${v.id} ${v.frame||''} ${v.text}`.toLowerCase().includes(search.toLowerCase()));}
function research(){
 const p=state.package,shown=filteredReadings(),v=p.variants.find(v=>v.id===inspected),controls=p.variants.filter(isControl).length,completed=p.variants.filter(comparisonComplete).length;
 const counts=['stable','sensitive','changed'].map(k=>[k,p.variants.filter(v=>v.outcome===k&&!isControl(v)).length]);
 return `<div class="research-intro"><p>Compare wording, inspect changes, and return to the original evidence.</p>${button('analysis','Export analysis')}</div><div class="three-col research-layout">${evidence()}<div class="col-main"><div class="panel-label">FULL PERTURBATION SET · K = ${p.variants.length}</div><div class="analysis-completion"><strong>${completed} / ${p.variants.length} ${p.game?.referenceOnly?'local ':''}comparisons complete</strong><span>${p.variants.length-controls} wording variants${controls?` · ${controls} controls`:''}${p.variants.length-completed?` · ${p.variants.length-completed} awaiting comparison`:''}</span></div><div class="metrics-row">${counts.map(([k,n])=>`<div class="metric"><p class="num ${k}">${n}</p><h4>${k==='changed'?'Recommendation changed':k==='stable'?'Stable':'Sensitive'}</h4></div>`).join('')}</div>${card(`${p.variants.length} readings. One evidence set.`,`${p.preparation?.perturbationGeneration?.shortfall?`<p class="alert-box">Generated ${p.preparation.perturbationGeneration.generated} of ${p.preparation.perturbationGeneration.target} distinct wording candidates. No formatting fillers were added; more source claims or a semantic generator are needed for the remaining candidates.</p>`:''}<p class="sub">Select a cell to compare its baseline and perturbed wording. ${controls?`${controls} saved formatting controls are compared separately and excluded from wording-stability totals.`:'All generated runs are wording substitutions, with no formatting fillers. Semantic equivalence still needs validation.'}</p><div id="variant-matrix">${variantMatrix(shown)}</div><div class="matrix-legend">${['stable','sensitive','changed','control','unscored','rejected'].map(k=>badge(k,['stable','sensitive','changed'].includes(k)||k==='control'?k:'neutral')).join('')}</div>`)}${card('Compare variant outcomes',`<div class="form-grid"><label>Outcome<select id="outcome-filter">${['all','stable','sensitive','changed','controls','unscored','rejected'].map(k=>`<option ${filter===k?'selected':''}>${k}</option>`).join('')}</select></label><label>Find a reading<input id="reading-search" value="${esc(search)}" type="search" placeholder="ID, frame, or wording"></label></div><div id="reading-results">${variantRows(shown)}</div>`)}${card('Reading the result','<p>Stable compares the tested game and plan. Sensitive and changed outcomes require upstream evidence; missing values are not invented.</p><p>Local formatting controls are not validated paraphrases. Their results do not establish semantic robustness or predict human behavior.</p>')}</div><aside class="col-side"><div class="panel-label">VARIANT INSPECTOR</div>${card(v?.frame||'Select a reading',v?`<p>${readingBadge(v)} <span class="mono" title="${esc(v.id)}">V${String(p.variants.indexOf(v)+1).padStart(3,'0')}</span></p><h4>Baseline</h4><blockquote>${esc(p.facts.find(f=>f.id===v.factId)?.text)}</blockquote><h4>Perturbed wording</h4><blockquote>${esc(v.text)}</blockquote><h4>Validation</h4><p>${esc(v.validation||'Not supplied.')}</p>`:empty('Select a matrix cell or table row.'))}${v?card('What moved?',`<h4>Before</h4><p>${esc(v.baselineNextMove||'Baseline next move not supplied.')}</p><div class="comparison-arrow" aria-hidden="true">↓</div><h4>After</h4><p>${esc(v.nextMove||'Next move not supplied.')}</p><hr><p>${esc(v.effect||'No comparison supplied.')}</p><p class="note-sm">${esc(v.method||'Upstream result')}</p>`):''}</aside></div>`;
}
function variantMatrix(rows){
 if(!rows.length)return empty(state.package.variants.length?'No readings match these filters.':'No readings yet. Run Prepare package first.');
 return `<div class="matrix-scroll"><div class="analysis-matrix" aria-label="Perturbation results">${Array.from({length:Math.ceil(rows.length/16)},(_,r)=>`<div class="matrix-band"><span class="matrix-range">${String(r*16+1).padStart(3,'0')}–${String(Math.min((r+1)*16,rows.length)).padStart(3,'0')}</span><div class="matrix-band-cells">${rows.slice(r*16,r*16+16).map(v=>`<button type="button" class="matrix-cell ${readingClass(v)} ${v.id===inspected?'selected':''}" data-reading="${esc(v.id)}" aria-label="${esc(v.id)}: ${esc(readingLabel(v))}" aria-pressed="${v.id===inspected}" title="${esc(v.frame||v.id)} · ${esc(readingLabel(v))}">${String(state.package.variants.indexOf(v)+1).padStart(3,'0')}</button>`).join('')}</div></div>`).join('')}</div></div>`;
}
function variantRows(rows){
 if(!rows.length)return empty('No readings match.');
 analysisPage=Math.min(analysisPage,Math.max(0,Math.ceil(rows.length/5)-1));const start=analysisPage*5;
 return `<div class="analysis-table-scroll"><table class="analysis-table"><thead><tr><th>Variant</th><th>Wording frame</th><th>Priority shift</th><th>Next move</th><th>Outcome</th></tr></thead><tbody>${rows.slice(start,start+5).map(v=>`<tr class="${v.id===inspected?'selected':''}"><td><button class="btn-ghost-link" data-reading="${esc(v.id)}" title="${esc(v.id)}">V${String(state.package.variants.indexOf(v)+1).padStart(3,'0')}</button></td><td><button class="variant-frame" data-reading="${esc(v.id)}">${esc(v.frame||'Supplied rewording')}</button><small>${esc(['formatting-control','same-text-control'].includes(v.method)?'Control · excluded from outcome totals':v.method||'Upstream result')}</small></td><td>${esc(v.priorityShift||'Not modeled')}</td><td><span class="next-move-summary">${esc(v.nextMove||'Not supplied')}</span></td><td>${readingBadge(v)}</td></tr>`).join('')}</tbody></table></div><div class="analysis-pagination"><span>${start+1}–${Math.min(start+5,rows.length)} of ${rows.length}</span><div class="action-group"><button class="btn" data-reading-page="-1" ${analysisPage===0?'disabled':''}>Previous</button><button class="btn" data-reading-page="1" ${start+5>=rows.length?'disabled':''}>Next →</button></div></div>`;
}
function bindResearchRows(){
 document.querySelectorAll('[data-reading]').forEach(el=>el.onclick=()=>{inspected=el.dataset.reading;render();});
 document.querySelectorAll('[data-reading-page]').forEach(el=>el.onclick=()=>{analysisPage+=Number(el.dataset.readingPage);document.getElementById('reading-results').innerHTML=variantRows(filteredReadings());bindResearchRows();});
}
function landing() { return `<section class="upload-welcome" aria-labelledby="upload-title"><div class="upload-mark" aria-hidden="true">↗</div><p class="note-sm">NEGOTIATION ADVISOR</p><h1 id="upload-title">Start with your documents</h1><p>Upload your negotiation package to prepare your case.</p>${button('pdf', 'Upload source package', true)}<p class="note-sm">PDF or Word documents</p><div class="welcome-secondary">${button('import', 'Import package JSON')}${button('example', 'Explore example workspace')}</div></section>`; }

function render() {
  if(VoiceCapture.active)VoiceCapture.stop();
  const p = state.package;
  document.getElementById('app').classList.toggle('landing-screen', !p);
  document.getElementById('app').innerHTML = `<header class="app-nav"><div class="brand"><div class="brand-mark">↗</div><div class="brand-text"><p class="name">Perturbation-Robust</p><p class="tagline">NEGOTIATION ADVISOR</p></div></div><nav class="workspace-nav" aria-label="Workspace">${[['prep', 'Preparation'], ['classroom', 'Negotiation'], ['admin', 'Research']].map(([key, text]) => `<button class="tab-btn ${state.view === key ? 'active' : ''}" data-view="${key}" aria-current="${state.view === key ? 'page' : 'false'}">${text}</button>`).join('')}</nav>${button('pdf', 'Upload documents')}${!p?button('import','Open saved workspace'):''}</header><main class="workspace"><div id="notice" role="status" aria-live="polite">${esc([message, storageWarning].filter(Boolean).join(' '))}</div>${p ? `<div class="page-intro"><div class="copy">${p.example?'<p class="eyebrow">Example case</p>':''}<h1 class="page-title">${state.view==='prep'?'Prepare for the conversation.':state.view==='classroom'?(pending?'Review the event before it counts.':'Negotiate with the facts in view.'):'Measure what the wording moves.'}</h1><p class="page-subtitle">${esc(p.title)}</p><p class="case-parties">${esc(p.parties.us)} ↔ ${esc(p.parties.opponent)}</p></div><div class="intro-actions">${button('export', 'Save workspace')}<details class="workspace-tools"><summary>Workspace options</summary>${button('import','Import workspace')}${button('template','Package format')}${button('reset','Clear workspace')}</details></div></div>${p.game?.referenceOnly?'<details class="simulation-notice"><summary>Local engine simulation · illustrative scores</summary><p>These actions confirm source interpretations. Scores and commitments are simulated; they are not a validated model of the real negotiation.</p></details>':''}${state.view === 'prep' ? prep() : state.view === 'classroom' ? live() : research()}` : landing()}</main><footer class="app-footer"><span>Human-led negotiation · Saved locally in this browser</span></footer>${pdfDialog()}<input type="file" id="package-file" accept=".json,application/json" hidden><dialog id="replace-dialog"><h2>Replace this workspace?</h2><p>A different package clears the current session. Export it first if you need to keep it.</p><div class="row-actions">${button('cancel-replace', 'Cancel')}${button('replace', 'Replace workspace', true)}</div></dialog>`;
  bind();
  LiveStrategy.schedule();
}
let incoming = null, pendingRestore = null;
function install(p) {
  const same = state.package?.id === p.id;
  if (same && state.session && !pendingRestore) {
    for (const id of [...state.session.commitments, ...state.session.events.flatMap(e => e.actionIds)]) {
      const old = state.package.actions.find(a => a.id === id), next = p.actions.find(a => a.id === id);
      if (!next || ['label', 'owner', 'factId'].some(k => old[k] !== next[k])) throw new Error('This update changes actions used in the session. Export and clear the workspace before importing it.');
    }
  }
  if (same && !p.preparation && state.package.preparation && p.sources.length === state.package.sources.length && p.sources.every(s => state.package.sources.some(old => old.id === s.id && old.text === s.text))) p.preparation = structuredClone(state.package.preparation);
  if (!same) { prepController?.abort(); prepRunToken++; }
  ensurePreparation(p);
  state.package = p;
  if (!same) { state.session = null; state.selected = null; state.view = 'prep'; }
  if (pendingRestore) { state.session = pendingRestore.session; state.selected = pendingRestore.selected; pendingRestore = null; }
  if (!p.strategies.some(s => s.id === state.selected)) state.selected = null;
  pending = draft = null; inspected = null; workspaceInferenceProgress={}; prepTab = 'overview'; docId = null; docQuery = ''; message = ''; save(); render();
  if (!same && p.sources.length && !p.strategies.length && !p.preparation.engines?.game?.startsWith('builtin:')) queueMicrotask(() => { runPreparation().catch(error); });
}
function receive(p) { M.validate(p); if (state.package && state.package.id !== p.id) { incoming = p; document.getElementById('replace-dialog').showModal(); } else install(p); }
function error(e) { message = e.message || String(e); const n = document.getElementById('notice'); n.textContent = message; n.scrollIntoView({ block: 'nearest' }); }
function bind() {
  bindPdfUpload();
  VoiceCapture.bind();
  bindPreparation();
  document.querySelectorAll('[data-view]').forEach(el => el.onclick = () => { state.view = el.dataset.view; message = ''; save(); render(); });
  document.querySelectorAll('[data-select]').forEach(el => el.onclick = () => { state.selected = el.dataset.select; state.package.preparation.chosenStrategyId = state.selected; save(); render(); });
  bindResearchRows();
  document.querySelectorAll('[data-action]').forEach(el => el.onclick = () => { Promise.resolve().then(() => action(el.dataset.action)).catch(error); });
  document.getElementById('package-file').onchange = async e => {
    try { const file = e.target.files[0]; if (!file) return; if (file.size > 25 * 1024 * 1024) throw new Error('Package is larger than 25 MB. Supply a smaller text snapshot.'); const imported = JSON.parse(await file.text());
      if (imported.packageId && !imported.package) { mergeEngineResult(imported); return; }
      if (imported.package) {
        M.validate(imported.package);
        let restored = imported.session ? { ...imported.session, events: [], commitments: [], running: false } : null;
        if (restored) {
          if (!Number.isFinite(restored.elapsed) || restored.elapsed < 0 || !Number.isFinite(restored.duration) || restored.duration <= 0) throw new Error('Invalid session timer.');
          for (const event of imported.session.events) restored = M.applyEvent(restored, event, imported.package);
        }
        pendingRestore = { selected: imported.selected, session: restored }; receive(imported.package);
      } else { pendingRestore = null; receive(imported); } } catch (err) { pendingRestore = null; error(err); } finally { e.target.value = ''; }
  };
  document.getElementById('event-form')?.addEventListener('input', e => {
    const data = new FormData(e.currentTarget);
    draft = { type: data.get('type'), speaker: data.get('speaker'), text: data.get('text'), offerId: data.get('offerId'), actionIds: data.getAll('actionIds') };
  });
  document.getElementById('event-form')?.addEventListener('change',e=>{if(['type','speaker'].includes(e.target.name)){if(draft&&!['accept','reject'].includes(draft.type))draft.offerId='';render();}});
  document.getElementById('event-form')?.addEventListener('submit', e => {
    e.preventDefault(); try {
      if(VoiceCapture.active)throw new Error('Stop recording and check the transcript before reviewing.');
      const data = new FormData(e.target);
      draft = { type: data.get('type'), speaker: data.get('speaker'), text: data.get('text').trim(), actionIds: data.getAll('actionIds'), offerId: data.get('offerId') };
      if (['accept', 'reject'].includes(draft.type)) { const offer = state.session.events.find(x => x.id === draft.offerId); draft.actionIds = draft.type === 'accept' ? [...(offer?.actionIds || [])] : []; }
      if (['note','question','tentative','unmodeled'].includes(draft.type)) draft.actionIds = [];
      M.applyEvent(state.session, draft, state.package);
      pending = { ...draft, actionIds: [...draft.actionIds], ...(VoiceCapture.metadata()?{capture:VoiceCapture.metadata()}:{} ) }; save(); render();
    } catch (err) { error(err); }
  });
  document.getElementById('outcome-filter')?.addEventListener('change', e => { filter = e.target.value; analysisPage=0; render(); });
  document.getElementById('reading-search')?.addEventListener('input', e => {
    search = e.target.value;analysisPage=0;const rows=filteredReadings();
    document.getElementById('reading-results').innerHTML = variantRows(rows);
    document.getElementById('variant-matrix').innerHTML = variantMatrix(rows);
    bindResearchRows();
  });
}
async function action(a) {
  if (await preparationAction(a)) return;
  switch (a) {
    case 'pdf': document.getElementById('pdf-dialog').showModal(); break;
    case 'import': document.getElementById('package-file').click(); break;
    case 'example': { const r = await fetch('example-package.json'); if (!r.ok) throw new Error('Example package could not load.'); receive(await r.json()); break; }
    case 'template': { const r = await fetch('example-package.json'); if (!r.ok) throw new Error('Template could not load.'); download('package-template.json', await r.json()); break; }
    case 'replace': install(incoming); incoming = null; break;
    case 'cancel-replace': incoming = null; pendingRestore = null; document.getElementById('replace-dialog').close(); break;
    case 'prep': state.view = 'prep'; save(); render(); break;
    case 'start-rehearsal':
      if(!state.package.sources.length)throw new Error('Upload sources before starting a rehearsal.');
      stopPreparation('Team started a source-only rehearsal.',false);
      if(!state.session)state.session={packageId:state.package.id,mode:'source-rehearsal',strategyId:null,startedAt:new Date().toISOString(),elapsed:0,duration:15*60,running:true,ended:false,events:[],commitments:[]};
      pending=draft=null;lastTick=Date.now();state.view='classroom';message='Source-only rehearsal. Confirmed notes preserve the conversation; game-based advice is unavailable.';save();render();break;
    case 'start':
      if (!state.session && state.package.preparation?.modelStale) throw new Error('The game is stale after a source correction. Rebuild it before starting.');
      if (!state.session && !selected()) throw new Error('Select a strategy first.');
      if (!state.session) state.session = { packageId: state.package.id, strategyId: state.selected, startedAt: new Date().toISOString(), elapsed: 0, duration: 15 * 60, running: true, ended: false, events: [], commitments: [] };
      lastTick = Date.now(); state.view = 'classroom'; save(); render(); break;
    case 'pause': if (!state.session.ended) { state.session.running = !state.session.running; lastTick = Date.now(); save(); render(); } break;
    case 'end': state.session.running = false; state.session.ended = true; pending = draft = null; save(); render(); break;
    case 'edit': pending = null; render(); break;
    case 'confirm': if (!pending || state.session.ended) throw new Error('No event to confirm.'); state.session = M.applyEvent(state.session, pending, state.package); pending = draft = null; VoiceCapture.clear(); message = 'Event confirmed. Strategy guidance updates in the background.'; save(); render(); break;
    case 'export': download('negotiation-workspace.json', state); break;
    case 'analysis': download('rewording-analysis.json', { packageId: state.package.id, pipeline: state.package.pipeline || [], variants: state.package.variants, strategies: state.package.strategies }); break;
    case 'print': { const s = selected(); if (!s) break; const region = document.createElement('section'); region.id = 'print-brief'; region.innerHTML = `<h1>${esc(state.package.title)}</h1>${brief(s)}<h4>Walk-away point</h4><p>${esc(state.package.walkAway || 'Not supplied')}</p>`; document.body.append(region); window.print(); region.remove(); break; }
    case 'reset': incoming = null; document.getElementById('replace-dialog').querySelector('h2').textContent = 'Clear this workspace?'; document.getElementById('replace-dialog').querySelector('[data-action="replace"]').onclick = () => { state = { package: null, selected: null, session: null, view: 'prep' }; pending = draft = null; message = 'Workspace cleared.'; save(); render(); }; document.getElementById('replace-dialog').showModal(); break;
  }
}
let lastTick = Date.now();
setInterval(() => {
  const now = Date.now(), delta = Math.floor((now - lastTick) / 1000); if (!delta) return; lastTick += delta * 1000;
  const s = state.session; if (!s?.running || s.ended) return;
  s.elapsed = Math.min(s.duration, s.elapsed + delta); if (s.elapsed === s.duration) { s.running = false; message = 'Session time reached. Review the log and end the session when ready.'; save(); render(); return; }
  const clock = document.getElementById('clock'); if (clock) clock.innerHTML = `${fmt(s.elapsed)} <span>/ ${fmt(s.duration)}</span>`;
  const status = document.getElementById('clock-status'); if (status) status.textContent = `Running · ${Math.ceil((s.duration - s.elapsed) / 60)} min remaining`; save();
}, 1000);
render();
window.workspaceStarted = true;

if (state.package?.preparation?.engines?.game && !state.package.preparation.engines.game.startsWith('builtin:') && !state.package.actions.length && !state.package.preparation.run) queueMicrotask(() => runPreparation().catch(error));
