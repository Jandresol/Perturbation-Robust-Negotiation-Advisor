/* Editable case interpretation. Source quotes and confirmed commitments are immutable here. */
(function(root){
 function hydrate(p){
  const c=p.sourceAnalysis?.caseAnalysis;if(!c)return p;
  const edited=p.caseEdits?.history?.some(x=>['context','team-context'].includes(x.kind));
  if(!edited){
   if((!p.title||p.title==='Negotiation package')&&c.title)p.title=c.title;
   const unknown=x=>!x||/not inferred|^(our side|our team|other team|opponent)$/i.test(x);
   if(c.our_side&&unknown(p.parties.us))p.parties.us=c.our_side;
   if(c.opponent&&unknown(p.parties.opponent))p.parties.opponent=c.opponent;
   if(!p.objective&&c.objective)p.objective=c.objective;
   if(!p.walkAway&&c.outside_option)p.walkAway=c.outside_option;
  }
  return p;
 }
 function redLines(p){
  return p.caseEdits?.redLines ?? (p.sourceAnalysis?.caseAnalysis?.red_lines||[]).map((r,i)=>({id:`red-line-${i+1}`,text:r.text,factIds:[...r.claim_ids],status:'inferred'}));
 }
 function reviseFact(p,id,text,reason){
  const next=structuredClone(p),fact=next.facts.find(f=>f.id===id);
  if(!fact||!text.trim()||!reason.trim())throw new Error('Provide a claim correction and a reason.');
  if(text.trim()===fact.text)return next;
  next.caseEdits ||= {};next.caseEdits.history ||= [];
  next.caseEdits.history.push({kind:'claim',id,before:fact.text,after:text.trim(),reason:reason.trim(),at:new Date().toISOString()});
  fact.text=text.trim();fact.corrected=true;next.preparation ||= {};next.preparation.modelStale=true;
  return next;
 }
 function reviseRedLine(p,id,text,status,factIds){
  if(!text.trim()||!['inferred','confirmed','dismissed'].includes(status)||factIds.some(id=>!p.facts.some(f=>f.id===id)))throw new Error('Provide a red line, valid status, and valid supporting facts.');
  const next=structuredClone(p),lines=redLines(next),before=lines.find(r=>r.id===id);
  const line={id,text:text.trim(),status,factIds:[...factIds]};
  next.caseEdits ||= {};next.caseEdits.redLines=before?lines.map(r=>r.id===id?line:r):[...lines,line];
  next.caseEdits.history ||= [];next.caseEdits.history.push({kind:'red_line',id,before:before||null,after:line,at:new Date().toISOString()});
  next.preparation ||= {};next.preparation.modelStale=true;
  return next;
 }
 const api={hydrate,redLines,reviseFact,reviseRedLine};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 if(typeof window!=='undefined')root.CaseModel=api;
})(typeof window!=='undefined'?window:globalThis);
