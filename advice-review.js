/* Conservative, local consistency checks. Not a semantic compliance certificate. */
const AdviceReview=(()=>{
 const clean=x=>String(x||'').replace(/\s*\(inferred[^)]*\)/gi,'').trim();
 const terms=x=>new Set(clean(x).toLowerCase().replace(/payments?|compensat\w*|wages?|rations?/g,' pay ').replace(/guards?/g,' guard ').match(/[a-z]{4,}/g)||[]);
 function constraints(p){
  if(p.caseEdits?.redLines)return p.caseEdits.redLines.filter(x=>x.status!=='dismissed').map(x=>({text:x.text,status:x.status,factIds:x.factIds||[]}));
  const c=p.sourceAnalysis?.caseAnalysis;
  return (c?.brief?.our_constraints?.length?c.brief.our_constraints:c?.red_lines||p.preparation?.brief?.redLines?.map(text=>({text}))||[]).filter(x=>x.status!=='unknown').map(x=>({text:x.text,status:x.status==='supported'?'supported':'inferred',force:x.force,factIds:[...(x.claim_ids||[]),...(x.source_passage_ids||[])]}));
 }
 function check(text,p){
  if(!text)return {status:'unknown',label:'Unknown',text:''};
  const base=clean(text);
  for(const c of constraints(p)){
   const foodLimit=/food|ration|in.kind/i.test(c.text)&&/pay|payment|compensat/i.test(c.text)&&/prohibit|forbid|must not|cannot|no direct|not permit/i.test(c.text);
   if(!foodLimit)continue;
   // Only an explicit proposed prohibited transaction blocks advice. Shared vocabulary is not contradiction.
   const clauses=base.split(/[.;!?]+/);
   for(const clause of clauses){
    if(!/guard/i.test(clause)||!/food|ration|in.kind/i.test(clause)||!/pay|payment|compensat/i.test(clause))continue;
    const excludes=/(?:no|not|without|avoid\w*|exclud\w*|prohibit\w*|refus\w*|forbid\w*|reject\w*|prevent\w*|rather than|instead of|do not|cannot)[^.;!?]{0,100}(?:pay|payment|compensat)|(?:pay|payment|compensat)[^.;!?]{0,60}(?:not permitted|prohibited|forbidden|unacceptable)/i.test(clause);
    const reports=/(?:commander|other side|counterpart|guards?)\s+(?:demands?|insists?|requests?|requires?)|explain[^.;!?]*(?:conflict|policy)/i.test(clause);
    const proposes=/\b(pay(?:ing)?|compensate|food payment scheme|payment scheme|offer[^.;!?]*food|agree[^.;!?]*food|accept[^.;!?]*food)\b/i.test(clause);
    if(proposes&&!excludes&&!reports)return {status:'conflict',label:'Do not use under the stated policy',text:base,constraint:c,reason:'This option explicitly proposes compensating guards with food; the stated policy prohibits that transaction.'};
   }
  }
  if(/\bguards?\b/i.test(base)&&/cash|wages?|pay|compensat/i.test(base)&&!/(?:no|without|avoid\w*|exclud\w*)[^.;!?]{0,100}(?:pay|payment|compensat)/i.test(base))return {status:'clarify',label:'Confirm permitted compensation first',text:base};
  return {status:'suggested',label:'Suggested approach',text:base};
 }

 function sources(p,ids=[]){return contextEvidence(p,ids,'Evidence');}

 function reviewed(p){const b=PrepWorkflow.draftBrief(p),openingReview=check(b.opening,p),fallbackReview=check(b.fallback,p),alternativeReviews=b.alternatives.map(t=>check(t,p)),branchReviews=b.branches.map(t=>check(t,p));return {...b,opening:openingReview.status==='conflict'?null:b.opening,fallback:fallbackReview.status==='conflict'?null:b.fallback,alternatives:alternativeReviews.filter(x=>x.status!=='conflict').map(x=>x.text),branches:branchReviews.filter(x=>x.status!=='conflict').map(x=>x.text),openingReview,fallbackReview,alternativeReviews,branchReviews};}

 function agenda(p){
  return p.sourceAnalysis?.caseAnalysis?.negotiation_issues||[];
 }
 return {clean,constraints,check,sources,reviewed,agenda};
})();
function decisionAgenda(p){return detailedNegotiationIssues(p);}
