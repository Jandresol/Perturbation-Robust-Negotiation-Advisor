/* Decision review, not a claim approval queue. No model calls or automatic clearance. */
function preparationIssues(p){
 const items=[],seen=new Set(),c=p.sourceAnalysis?.caseAnalysis||{},b=PrepWorkflow.draftBrief(p);
 const hash=text=>{let n=2166136261;for(const ch of text)n=Math.imul(n^ch.charCodeAt(0),16777619);return (n>>>0).toString(16);};
 const add=(x)=>{const key=x.detail.trim().replace(/\s+/g,' ').toLowerCase();if(seen.has(key))return;seen.add(key);const id='review-'+hash(x.category+'|'+key);items.push({...x,id,review:p.preparation?.issueReviews?.[id]||{status:'open',note:''}});};
 if(!p.objective&&!c.objective)add({category:'Decisions',severity:'high',title:'Define the objective',detail:'The outcome our team is seeking is missing.',action:'Set a specific desired outcome in case details.'});
 if(!p.walkAway&&!c.outside_option)add({category:'Decisions',severity:'medium',title:'Establish the outside option',detail:'What we can do without an agreement is unknown.',action:'Agree on a feasible alternative with your team; do not invent one from an empty commitment state.'});
 if(!b.authority?.text||b.authority.status==='unknown')add({category:'Decisions',severity:'medium',title:'Confirm decision authority',detail:b.authority?.text||'Who can approve the proposed terms has not been established.',action:'Ask who can authorize each side’s commitments and which approvals are required.'});
 if(b.briefStale||p.preparation?.modelStale)add({category:'Model & guidance',severity:'high',title:'Guidance is out of date',detail:'Case decisions or source claims changed after the current guidance was prepared.',action:'Refresh the brief or rebuild modeled options before relying on them.'});
 for(const x of PrepWorkflow.issues(p)){
  const model=['Game assumption','Advisory concern'].includes(x.title),evidence=!!x.sourceId;
  if(model&&p.game?.referenceOnly)continue;
  add({...x,category:evidence?'Evidence':model?'Model & guidance':'Decisions',severity:evidence?'high':model?'medium':x.id==='role'?'high':'medium',action:evidence?'Inspect the linked source and confirm the missing or uncertain evidence.':model?'Check this assumption with your team before relying on scored options.':'Clarify this point with the team or the other side; record what you learn.'});
 }
 if(p.game?.referenceOnly)add({category:'Model & guidance',severity:'info',title:'Simulation scores are illustrative',detail:'The local game tests reciprocal fact confirmations, not real case concessions.',action:'Use the document-based brief for the walkthrough; use a grounded game for meaningful strategy scores.'});
 const inferred=p.caseEdits?.redLines?p.caseEdits.redLines.filter(r=>r.status==='inferred'):(c.red_lines||[]);
 if(inferred.length)add({category:'Policy & limits',severity:'medium',title:'Confirm inferred red lines',detail:`${inferred.length} inferred limits need team confirmation.`,action:'Check ownership, scope, and exceptions in case details. A source-grounded inference is not an authorized policy decision.'});
 for(const t of c.brief?.tradeoffs||[])if(/contradict|violat|forbid|non.?complian/i.test(t.risk||''))add({category:'Policy & limits',severity:'high',title:'Potential policy conflict in generated advice',detail:`${t.proposal} — ${t.risk}`,factIds:t.claim_ids,action:'Exclude the conflicting suggestion from your opening. Verify the policy with its owner; do not treat generated advice as approval.'});
 return items.sort((a,b)=>({high:0,medium:1,info:2}[a.severity]-{high:0,medium:1,info:2}[b.severity]));
}
function negotiationIssuesMarkup(p){return decisionAgenda(p);}
function preparationIssueMarkup(p){
 const issues=preparationIssues(p),open=issues.filter(x=>x.review.status!=='reviewed');
 return `<p class="note-sm">${open.length} open checks · ${open.filter(x=>x.severity==='high').length} high priority. Team review records a judgment; it does not certify the evidence or model.</p>${['Decisions','Policy & limits','Evidence','Model & guidance'].map(category=>{
  const group=issues.filter(x=>x.category===category);if(!group.length)return '';
  return `<section class="issue-category"><h3>${category} <small>(${group.length})</small></h3>${group.map(x=>`<details class="issue-review" data-issue-id="${x.id}"><summary>${badge(x.severity,x.severity==='high'?'changed':'neutral')} <strong>${esc(x.title)}</strong> <span>${esc(x.review.status==='reviewed'?'Reviewed':x.review.status==='needs-input'?'Needs input':'Open')}</span></summary><p>${esc(x.detail)}</p><p><strong>Next action:</strong> ${esc(x.action)}</p>${x.sourceId?citation(p,x):''}${(x.factIds||[]).map(id=>p.facts.find(f=>f.id===id)).filter(Boolean).map(f=>citation(p,f)).join('')}<form data-issue-review="${x.id}"><label>Team status<select name="status"><option value="open" ${x.review.status==='open'?'selected':''}>Open</option><option value="needs-input" ${x.review.status==='needs-input'?'selected':''}>Needs input</option><option value="reviewed" ${x.review.status==='reviewed'?'selected':''}>Reviewed by team</option></select></label><label>What did you establish?<textarea name="note" rows="2" maxlength="2000" placeholder="Record evidence, an answer, or who will follow up.">${esc(x.review.note)}</textarea></label><button type="submit" class="btn">Save review</button></form></details>`).join('')}</section>`;
 }).join('')||empty('No specific issues detected. Confirm your objective, authority, and limits with the team.')}`;
}
function bindIssueReviews(){document.querySelectorAll('[data-issue-review]').forEach(form=>form.onsubmit=e=>{
 e.preventDefault();const data=new FormData(form),status=data.get('status'),note=data.get('note').trim();
 if(status==='reviewed'&&!note){form.querySelector('[name=note]').setCustomValidity('Record the basis for your review.');form.querySelector('[name=note]').reportValidity();return;}
 state.package.preparation.issueReviews||={};state.package.preparation.issueReviews[form.dataset.issueReview]={status,note,at:new Date().toISOString()};save();render();
 form.querySelector('[name=note]').setCustomValidity('');
 });document.querySelectorAll('[data-issue-review] textarea').forEach(el=>el.oninput=()=>el.setCustomValidity(''));}
