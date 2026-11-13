/* Latest-request-wins worker updates; never rerender the recording form. */
const LiveStrategy=(()=>{
 let key='',worker=null,timer=null,result=null,status='idle',generation=0,request=null,model=null,modelStatus='idle';
 function paint(){const el=document.querySelector('.strategy-guidance');if(el){const opened=[...el.querySelectorAll('details[data-guidance-section][open]')].map(d=>d.dataset.guidanceSection);el.outerHTML=guidance();for(const id of opened)document.querySelector(`[data-guidance-section="${id}"]`)?.setAttribute('open','');bindGuidanceUI();document.querySelectorAll('.strategy-guidance [data-citation-source]').forEach(link=>link.onclick=()=>{openSourceInspection(link.dataset.citationSource,link.dataset.citationFact);});}}
 // What the model reads: the reviewed brief, the prepared issues and the confirmed conversation. No raw documents.
 function context(p,s,b){
  const c=p.sourceAnalysis?.caseAnalysis||{},entries=v=>(v||[]).map(e=>({text:e.text,claim_ids:e.claim_ids||[]}));
  return {parties:p.parties,objective:p.objective||c.objective||b.objective||null,
   brief:{opening:b.opening,fallback:b.fallback,outside_option:b.outsideOption,red_lines:b.redLines,alternatives:b.alternatives,response_branches:b.branches,assumptions:b.assumptions,authority:b.authority?.text||null},
   issues:(c.negotiation_issues||[]).map(i=>({id:i.id,title:i.title,status:s.issueStatus?.[i.id]||'open',...Object.fromEntries(['decision','our_position','counterpart_position','our_reasons','counterpart_reasons','conditions','previous_alternatives','possible_arrangements'].map(k=>[k,entries(i[k])]))})),
   tentative_plan:(s.preparedPlan?.arrangements||[]).map(a=>a.text),
   conversation:s.events.map(e=>({id:e.id,speaker:p.parties[e.speaker],type:e.proposal?'proposal':e.type,text:e.text,issue:e.issueId||null})),
   current_proposal:s.currentProposal?{text:s.currentProposal.text,speaker:p.parties[s.currentProposal.speaker],status:s.currentProposal.status}:null,
   accepted_commitments:s.commitments.map(id=>p.actions.find(a=>a.id===id)?.label).filter(Boolean),boundary_checks:s.boundaryChecks||{}};
 }
 function askModel(p,s,b,token){
  const controller=new AbortController();request=controller;
  fetch('/api/live/advice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({context:context(p,s,b)}),signal:controller.signal})
   .then(async r=>{const data=await r.json();if(!r.ok)throw Error(data.error);return data;})
   .then(data=>{if(token!==generation)return;model={...data,events:s.events.length};modelStatus='ready';paint();})
   .catch(()=>{if(token!==generation)return;modelStatus='unavailable';paint();})
   .finally(()=>{if(request===controller)request=null;});
 }
 function schedule(){
  if(state.view!=='classroom'||!state.session||state.session.ended){worker?.terminate();clearTimeout(timer);request?.abort();worker=request=null;key='';generation++;status=modelStatus='idle';result=model=null;return;}
  const p=state.package,s=state.session,b=AdviceReview.reviewed(p);
  const nextKey=JSON.stringify([p.id,s.events,s.commitments,b,p.game,p.actions]);
  if(key===nextKey)return;
  key=nextKey;result=model=null;const token=++generation;worker?.terminate();clearTimeout(timer);request?.abort();status='updating';modelStatus=s.events.length?'updating':'idle';
  // The server finishes and caches an aborted call, so a superseded exchange is not billed twice.
  if(s.events.length)askModel(p,s,b,token);
  paint();
  try{
   worker=new Worker('live-strategy-worker.js?v=20261022-live1');
   const finish=(value,error)=>{if(token!==generation)return;clearTimeout(timer);worker?.terminate();worker=null;if(value)result=value;status=error?'limited':'ready';paint();};
   worker.onmessage=e=>finish(e.data,false);worker.onerror=()=>finish(null,true);
   timer=setTimeout(()=>finish(null,true),2500);
   const compact={parties:p.parties,walkAway:p.walkAway,game:p.game,actions:p.actions,facts:p.facts.map(({id,text,sourceId,category})=>({id,text,sourceId,category})),sources:p.sources.map(({id,visibility,category})=>({id,visibility,category}))};
   worker.postMessage({package:compact,session:s,brief:b});
  }catch{status='limited';paint();}
 }
 // Model advice replaces the rule-based next move; local questions and re-scored options stay as backup.
 return {schedule,repaint:paint,get current(){return model?{asks:[],options:[],...result,next:model.next_move,model,events:model.events}:result;},get status(){return status;},get modelStatus(){return modelStatus;}};
})();
