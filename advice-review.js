/* Conservative, local consistency checks. Not a semantic compliance certificate. */
const AdviceReview=(()=>{
 const clean=x=>String(x||'').replace(/\s*\(inferred[^)]*\)/gi,'').trim();
 const terms=x=>new Set(clean(x).toLowerCase().replace(/payments?|compensat\w*|wages?|rations?/g,' pay ').replace(/guards?/g,' guard ').match(/[a-z]{4,}/g)||[]);
 function constraints(p){
  if(p.caseEdits?.redLines)return p.caseEdits.redLines.filter(x=>x.status!=='dismissed').map(x=>({text:x.text,status:x.status,factIds:x.factIds||[]}));
  const c=p.sourceAnalysis?.caseAnalysis;
  return (c?.brief?.our_constraints?.length?c.brief.our_constraints:c?.red_lines||p.preparation?.brief?.redLines?.map(text=>({text}))||[]).map(x=>({text:x.text,status:'inferred',factIds:x.claim_ids||[]}));
 }
 function check(text,p){
  if(!text)return {status:'unknown',label:'Unknown',text:''};
  const negative=/\b(no|not|without|prohibit\w*|avoid\w*|refus\w*|forbid\w*)\b/i;
  const base=clean(text);
  if(/\bif\b.*\b(explain|clarify)\b.*\b(conflict|policy|limit)/i.test(base))return {status:'clarify',label:'Requires clarification and authorization',text:base};
  for(const c of constraints(p)){
   if(!negative.test(c.text))continue;
   // Match the prohibited transaction, keeping recipient distinctions intact.
   const foodPay=/food|ration|in.kind/i.test(c.text)&&/pay|payment|compensat/i.test(c.text)&&/food|ration|in.kind/i.test(base)&&/pay|payment|compensat/i.test(base);
   const sameRecipient=!/guard/i.test(c.text)||/guard/i.test(base);
   const guardException=/non.militia.*community|community.*non.militia/i.test(base)&&!/\bguards?\b/i.test(base);
   const a=terms(c.text),overlap=[...terms(base)].filter(x=>a.has(x)&&!['policy','must','that','with','have','from','food'].includes(x)).length;
   if((foodPay&&sameRecipient&&!guardException||overlap>=4)&&!negative.test(base))return {status:'conflict',label:'Conflicts with a stated limit',text:base,constraint:c};
  }
  if(/\bguards?\b/i.test(base)&&/cash|wages?|pay|compensat/i.test(base)&&!negative.test(base))return {status:'clarify',label:'Requires authorization',text:base};
  return {status:'suggested',label:'Suggested approach · check feasibility',text:base};
 }
 function sources(p,ids=[]){return contextEvidence(p,ids,'Evidence');}

 function reviewed(p){const b=PrepWorkflow.draftBrief(p),openingReview=check(b.opening,p),fallbackReview=check(b.fallback,p),alternativeReviews=b.alternatives.map(t=>check(t,p)),branchReviews=b.branches.map(t=>check(t,p));return {...b,opening:openingReview.status==='conflict'?null:b.opening,fallback:fallbackReview.status==='conflict'?null:b.fallback,alternatives:alternativeReviews.filter(x=>x.status!=='conflict').map(x=>x.text),branches:branchReviews.filter(x=>x.status!=='conflict').map(x=>x.text),openingReview,fallbackReview,alternativeReviews,branchReviews};}

 function agenda(p){
  const c=p.sourceAnalysis?.caseAnalysis||{},b=reviewed(p),a=c.brief||{};
  const buckets=[['Compensation & resources',/pay|wage|compensat|ration|fund|cost|budget|price/i],['Timing & prerequisites',/assess|donor|deadline|timing|delay|schedule|week|day|before/i],['Access, movement & security',/guard|escort|access|movement|secur|staff|protect/i],['Monitoring & safeguards',/monitor|diversion|oversight|neutral|independen|exploit|abuse/i]];
  const records=[{text:b.opening,kind:'proposal',ids:a.opening?.claim_ids||[]},{text:b.fallback,kind:'proposal',ids:a.fallback?.claim_ids||[]},...constraints(p).map(x=>({text:x.text,kind:'ours',ids:x.factIds})),...b.opponentDemands.map(x=>({text:x.text,kind:'theirs',ids:x.claim_ids||[]})),...(c.issues||[]).map(x=>({text:x.text,kind:'question',ids:x.claim_ids||[]}))].filter(x=>x.text);
  const groups=buckets.map(([title,pattern],index)=>({title,items:records.filter(x=>pattern.test(x.text)&&buckets.findIndex(([,test])=>test.test(x.text))===index)})).filter(g=>g.items.length);
  if(!groups.length&&records.length)groups.push({title:'Terms to agree',items:records});
  return groups.slice(0,4).map(g=>({...g,ours:g.items.find(x=>x.kind==='ours'),theirs:g.items.find(x=>x.kind==='theirs'),proposal:g.items.find(x=>x.kind==='proposal'&&check(x.text,p).status!=='conflict'),question:g.items.find(x=>x.kind==='question'),ids:[...new Set(g.items.flatMap(x=>x.ids))].slice(0,3)}));
 }
 return {clean,constraints,check,sources,reviewed,agenda};
})();
function decisionAgenda(p){
 const questions={'Compensation & resources':'What compensation or resources, if any, can our side authorize, for whom, and under which limits?','Timing & prerequisites':'Which prerequisites must be met before action, by when, and who can approve a changed timeline?','Access, movement & security':'Who controls access and movement, what security responsibilities would each party accept, and what safeguards are required?','Monitoring & safeguards':'How will the parties monitor delivery, prevent abuse or diversion, and respond if safeguards fail?'};
 return `<p class="note-sm">The decisions for this negotiation. General political context stays in Evidence unless its relevance to these decisions is established.</p>${AdviceReview.agenda(p).map((g,i)=>`<details class="case-agenda-item"><summary><strong>${i+1}. ${esc(g.title)}</strong></summary><dl><dt>Our position</dt><dd>${esc(g.ours?.text||'Confirm the position our representative is authorized to take.')}</dd><dt>Reported other-side position</dt><dd>${esc(g.theirs?.text||'Not established for this issue. Ask the counterpart directly.')}</dd><dt>Possible proposal</dt><dd>${esc(g.proposal?.text||'Clarify positions before proposing terms.')}${g.proposal?`<small>${AdviceReview.check(g.proposal.text,p).label}</small>`:''}</dd><dt>Question to settle</dt><dd>${esc(g.question?.text&&/\?\s*$/.test(g.question.text)?g.question.text:questions[g.title]||`What concrete terms can ${p.parties.us} and ${p.parties.opponent} authorize, and what approval is still needed?`)}</dd></dl>${AdviceReview.sources(p,g.ids)}</details>`).join('')||empty('Infer the case or edit your brief to establish the negotiation agenda.')}`;
}
