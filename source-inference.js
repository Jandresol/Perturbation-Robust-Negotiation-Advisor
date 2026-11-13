/* One streaming request: real per-document milestones, with JSON fallback for older servers. */
function inferenceProgressMarkup(sources,progress={}){
 const done=sources.filter(s=>progress[s.id]?.status==='complete').length;
 return `<section class="inference-progress" aria-label="Source analysis progress"><h4>Interpreting sources · ${done} of ${sources.length} complete</h4><progress max="${sources.length}" value="${done}" aria-label="Documents completed"></progress><p class="note-sm">Each source shows actual processing status. Model generation has no percentage estimate. Cached responses are reused.</p>${sources.map(s=>{const item=progress[s.id]||{},status=item.status||'queued';return `<div class="source-progress-row"><div><strong>${esc(s.title)}</strong><span>${esc(status==='complete'?(item.cacheHit?'Reused saved analysis':'Analyzed')+(item.claims!=null?` · ${item.claims} claims`:'')+(item.limitations?` · ${item.limitations} limitations`:''):status==='running'?'Analyzing or checking saved output…':status==='failed'?'Needs attention':status==='stopped'?'Stopped; paid outputs retained':'Queued')}</span></div><progress max="1" ${status==='running'?'':`value="${status==='complete'?1:0}"`} aria-label="${esc(s.title)}: ${status}"></progress></div>`;}).join('')}<p class="note-sm">Preparation brief and roles: ${progress.case?.status==='complete'?(progress.case.cacheHit?'reused saved interpretation':'complete'):progress.case?.status==='running'?'combining source analyses…':progress.stopped?'not completed':'waiting for source analyses'}</p></section>`;
}
async function requestSourceInference(packageData,signal,onProgress=()=>{}){
 const response=await fetch('/api/sources/parse',{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/x-ndjson'},body:JSON.stringify({package:packageData}),signal});
 if(!response.headers.get('Content-Type')?.includes('application/x-ndjson')){
  let result;try{result=await response.json();}catch{throw new Error('Inference API unavailable. Start the app with python3 server.py.');}
  if(!response.ok)throw new Error(result.error||`Inference returned HTTP ${response.status}.`);
  for(const doc of result.documents||[])onProgress({type:'source',sourceId:doc.sourceId,status:'complete',cacheHit:doc.cacheHit,claims:doc.analysis?.claims?.length});
  onProgress({type:'case',status:'complete',cacheHit:result.caseCacheHit});return result;
 }
 const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='',result;
 function consume(line){if(!line.trim())return;const event=JSON.parse(line);if(event.type==='error')throw new Error(event.error);if(event.type==='result')result=event.result;else onProgress(event);}
 try{while(true){const {done,value}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});let end;while((end=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,end);buffer=buffer.slice(end+1);consume(line);}}buffer+=decoder.decode();consume(buffer);if(!result)throw new Error('Analysis connection ended before completion. Saved outputs will be reused.');return result;}finally{reader.releaseLock();}
}
function updateInferenceProgress(progress,event){if(event.type==='source')progress[event.sourceId]=event;if(event.type==='case')progress.case=event;}
function stopInferenceProgress(progress){progress.stopped=true;for(const item of Object.values(progress))if(item?.status==='running')item.status='stopped';}
