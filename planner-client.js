/* Keep planning off the UI thread, including recovery from a stale worker URL. */
async function runPlannerWorker(packageData, commitments, {signal}={}) {
 const url=new URL('planner.js?v=20261023-planner1',location.href);
 let worker=null,blobUrl=null;
 const controller=new AbortController();
 const abort=()=>controller.abort();signal?.addEventListener('abort',abort,{once:true});
 if(signal?.aborted)controller.abort();
 const timeout=setTimeout(()=>controller.abort(new Error('Planning exceeded 30 seconds. Use a smaller game or external planner.')),30000);
 function attempt(workerUrl){return new Promise((resolve,reject)=>{
  if(controller.signal.aborted)return reject(controller.signal.reason||new Error('Preparation stopped.'));
  let settled=false;
  const finish=(error,value)=>{if(settled)return;settled=true;controller.signal.removeEventListener('abort',cancel);worker?.terminate();error?reject(error):resolve(value);};
  const cancel=()=>finish(controller.signal.reason||new Error('Preparation stopped.'));
  controller.signal.addEventListener('abort',cancel,{once:true});
  try{
   worker=new Worker(workerUrl);
   worker.onmessage=e=>{if(e.data?.ok)finish(null,e.data.result);else{const err=new Error(e.data?.error||'The planner returned an invalid response.');err.modelError=true;finish(err);}};
   worker.onerror=e=>{e.preventDefault();finish(new Error('Planner worker could not load.'));};
   worker.postMessage({package:packageData,commitments});
  }catch(err){finish(err);}
 });}
 try{
  try{return await attempt(url.href);}catch(error){
   if(controller.signal.aborted||error.modelError)throw error;
   // Fetch a fresh copy once. Do not retry model errors or run search on the UI thread.
   const response=await fetch(url,{cache:'no-store',signal:controller.signal});
   if(!response.ok)throw new Error(`Planner file is unavailable (HTTP ${response.status}). Restore the app branch and reload before building strategy options.`);
   blobUrl=URL.createObjectURL(new Blob([await response.text()],{type:'text/javascript'}));
   try{return await attempt(blobUrl);}catch(retryError){
    if(controller.signal.aborted||retryError.modelError)throw retryError;
    throw new Error('The browser could not start the planner. Reload the app and allow same-origin workers; your source draft is preserved.');
   }
  }
 }finally{clearTimeout(timeout);worker?.terminate();if(blobUrl)URL.revokeObjectURL(blobUrl);signal?.removeEventListener('abort',abort);}
}
