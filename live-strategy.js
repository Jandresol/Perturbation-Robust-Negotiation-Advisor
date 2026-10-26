/* Latest-request-wins worker updates; never rerender the recording form. */
const LiveStrategy=(()=>{
 let key='',worker=null,timer=null,result=null,status='idle',generation=0;
 function paint(){const el=document.querySelector('.strategy-guidance');if(el){const opened=[...el.querySelectorAll('details[data-guidance-section][open]')].map(d=>d.dataset.guidanceSection);el.outerHTML=guidance();for(const id of opened)document.querySelector(`[data-guidance-section="${id}"]`)?.setAttribute('open','');bindGuidanceUI();document.querySelectorAll('.strategy-guidance [data-citation-source]').forEach(link=>link.onclick=()=>{openSourceInspection(link.dataset.citationSource,link.dataset.citationFact);});}}
 function schedule(){
  if(state.view!=='classroom'||!state.session||state.session.ended){worker?.terminate();clearTimeout(timer);worker=null;key='';generation++;status='idle';result=null;return;}
  const p=state.package,s=state.session,b=AdviceReview.reviewed(p);
  const nextKey=JSON.stringify([p.id,s.events,s.commitments,b,p.game,p.actions]);
  if(key===nextKey)return;
  key=nextKey;result=null;const token=++generation;worker?.terminate();clearTimeout(timer);status='updating';paint();
  try{
   worker=new Worker('live-strategy-worker.js?v=20261022-live1');
   const finish=(value,error)=>{if(token!==generation)return;clearTimeout(timer);worker?.terminate();worker=null;if(value)result=value;status=error?'limited':'ready';paint();};
   worker.onmessage=e=>finish(e.data,false);worker.onerror=()=>finish(null,true);
   timer=setTimeout(()=>finish(null,true),2500);
   const compact={parties:p.parties,walkAway:p.walkAway,game:p.game,actions:p.actions,facts:p.facts.map(({id,text,sourceId,category})=>({id,text,sourceId,category})),sources:p.sources.map(({id,visibility,category})=>({id,visibility,category}))};
   worker.postMessage({package:compact,session:s,brief:b});
  }catch{status='limited';paint();}
 }
 return {schedule,repaint:paint,get current(){return result;},get status(){return status;}};
})();
