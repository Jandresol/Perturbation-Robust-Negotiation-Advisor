/* Same-origin engine jobs: polling never blocks recording or the preparation UI. */
async function runPeerEngine(engine,packageData,{signal,onProgress=()=>{}}={}){
 let jobId=null,complete=false;
 const cancel=()=>{if(jobId&&!complete)fetch(`/api/engines/jobs/${jobId}/cancel`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',keepalive:true}).catch(()=>{});};
 signal?.addEventListener('abort',cancel,{once:true});
 try{
  if(signal?.aborted)throw new DOMException('Preparation stopped.','AbortError');
  const response=await fetch('/api/engines/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({engine,packageId:packageData.id,package:packageData,factSetFrozen:engine==='perturbation'})});
  const started=await response.json();if(!response.ok)throw new Error(started.error||'Engine could not start.');jobId=started.jobId;
  if(signal?.aborted){cancel();throw new DOMException('Preparation stopped.','AbortError');}
  for(;;){
   const statusResponse=await fetch(`/api/engines/jobs/${jobId}`,{signal,cache:'no-store'});const job=await statusResponse.json();
   if(!statusResponse.ok)throw new Error(job.error||'Engine status unavailable.');onProgress(job.progress||{});
   if(job.status==='complete'){complete=true;return job.result;}
   if(['failed','cancelled'].includes(job.status))throw new Error(job.error||'Engine stopped. Your baseline is retained.');
   await new Promise((resolve,reject)=>{const abort=()=>{clearTimeout(timer);signal?.removeEventListener('abort',abort);reject(new DOMException('Preparation stopped.','AbortError'));};const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve();},500);signal?.addEventListener('abort',abort,{once:true});if(signal?.aborted)abort();});
  }
 }finally{signal?.removeEventListener('abort',cancel);if(!complete)cancel();}
}
function engineProgressText(progress){
 const phases={'loading-semantic-models':'Loading local similarity and entailment filters before any paid generation…','waiting-for-semantic-engine':'Waiting for the semantic engine…','building-game':'Building the teammate commitment game…','generating-and-filtering':'Generating, filtering, and comparing wordings…'};
 return `${phases[progress.phase]||'Engine running…'}${progress.unit?` Source claim ${progress.unit}/${progress.units}.`:''}${progress.accepted!=null?` ${progress.accepted} accepted wordings.`:''}`;
}
