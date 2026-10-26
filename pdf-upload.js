let uploadProgress={};
/* Upload first; category applies to a whole batch. API inference fills editable metadata. */
let pdfBatch = [], pdfAbort = null, pdfBusy = false, uploadAnalysis = null, inferredUploadValues = {};
const uploadGroups = { shared: 'Shared information', specific: 'Side-specific information', role_card: 'Our role card' };
const documentAccept = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';
function pdfDialog() {
  return `<dialog id="pdf-dialog"><form id="pdf-package-form"><h2>Upload your negotiation package</h2><p>Add any documents you have. Each upload category is optional. Add the package first, including our role card if available. Continue to infer the case and our role, then review the results.</p><div class="upload-groups">${Object.entries(uploadGroups).map(([key,label])=>`<section class="upload-group"><h3>${label}</h3><p>${key==='shared'?'Background and documents available to both sides.':key==='specific'?'Additional information available to our side.':'Instructions describing who we represent.'}</p><button type="button" class="btn" data-upload-group="${key}">Upload ${key==='role_card'?'role card':key==='specific'?'specific information':'shared information'}</button><input hidden type="file" id="${key==='shared'?'pdf-files':key+'-files'}" data-document-group="${key}" accept="${documentAccept}" multiple></section>`).join('')}</div><p class="note-sm">PDF and DOCX · up to 30 files, 20 MB each, 100 MB total. Side-specific information and role cards are private to our side. Inference uses the API; saved responses are reused and automatic paid retries are disabled.</p><div id="pdf-results" aria-live="polite"></div><button type="button" class="btn" id="upload-browse-raw" disabled>Browse raw sources</button><div id="upload-analysis" aria-live="polite"></div><section class="inferred-fields" hidden><h3>Case and roles</h3><p class="note-sm">Inferred from the package, prioritizing our role card. Correct anything that needs attention.</p><label>Case title<input name="title" maxlength="200" placeholder="Inferred from your package"></label><div class="form-grid"><label>Our side<input name="us" maxlength="150" placeholder="Inferred from our role card"></label><label>Opponent<input name="opponent" maxlength="150" placeholder="Inferred from the negotiation context"></label></div><label>Our objective<textarea name="objective" rows="2" maxlength="2000" placeholder="Inferred from our instructions and supporting evidence"></textarea></label></section><p id="pdf-error" role="alert"></p><div class="row-actions"><button type="button" class="btn" id="pdf-cancel">Cancel</button><button type="button" class="btn" id="sources-only" disabled>Continue with sources</button><button class="btn btn-primary" id="pdf-create" type="submit" disabled>Continue &amp; infer</button></div></form></dialog>`;
}
function uploadSources(){
  return pdfBatch.filter(x=>x.result).map(x=>({id:`source-${x.hash.slice(0,20)}`,fileHash:x.hash,title:x.file.name,category:x.category,visibility:x.category==='shared'?'shared':'private',text:x.result.text,format:x.result.format,pages:x.result.pages,sections:x.result.sections,emptyPages:x.result.emptyPages}));
}
function pdfResults(){
  const region=document.getElementById('pdf-results');if(!region)return;
  region.innerHTML=pdfBatch.map((item,i)=>`<article class="pdf-result"><div class="row-actions"><strong>${esc(item.file.name)}</strong><button type="button" class="btn-ghost-link" data-remove-document="${i}" ${pdfBusy?'disabled':''}>Remove</button></div>${badge(uploadGroups[item.category])}<p>${esc(item.status)}</p></article>`).join('');
  region.querySelectorAll('[data-remove-document]').forEach(el=>el.onclick=()=>{pdfBatch.splice(Number(el.dataset.removeDocument),1);invalidateUploadAnalysis();pdfResults();});
  pdfReady();
}
function pdfReady(){
  const readable=pdfBatch.some(x=>x.result);
  for(const id of ['pdf-create','sources-only']){const el=document.getElementById(id);if(el)el.disabled=pdfBusy||!readable;}
  document.querySelectorAll('[data-upload-group],[data-document-group]').forEach(el=>el.disabled=pdfBusy);
  const browse=document.getElementById('upload-browse-raw');if(browse)browse.disabled=!readable;
  const submit=document.getElementById('pdf-create');if(submit)submit.textContent=pdfBusy?'Processing documents…':uploadAnalysis?'Open preparation':'Continue & infer';
}
function invalidateUploadAnalysis(){
  const form=document.getElementById('pdf-package-form');
  for(const [name,value] of Object.entries(inferredUploadValues))if(form?.elements[name]?.value===value)form.elements[name].value='';
  updateRawProcessing('idle');inferredUploadValues={};uploadAnalysis=null;document.querySelector('.inferred-fields')?.setAttribute('hidden','');
  const panel=document.getElementById('upload-analysis');if(panel)panel.innerHTML='';
}
async function analyzeUploadedSources(signal){
  const sources=uploadSources();
  const result=await requestSourceInference({id:'intake',sources},signal,event=>{updateInferenceProgress(uploadProgress,event);document.getElementById('upload-analysis').innerHTML=inferenceProgressMarkup(sources,uploadProgress);});
  if(signal.aborted)throw new DOMException('Cancelled','AbortError');
  if(!Array.isArray(result.documents)||!Array.isArray(result.facts)||!result.caseAnalysis)throw new Error('The source API returned an incomplete package.');
  // Validate returned facts against the actual uploaded sources before installing them.
  M.validate({schemaVersion:1,id:'intake',title:'Intake',parties:{us:'Our side',opponent:'Opponent'},sources,facts:result.facts,actions:[],strategies:[],variants:[]});
  updateRawProcessing('complete');uploadAnalysis=result;document.querySelector('.inferred-fields')?.removeAttribute('hidden');
  const form=document.getElementById('pdf-package-form'),c=result.caseAnalysis;
  for(const [name,value] of Object.entries({title:c.title,us:c.our_side,opponent:c.opponent,objective:c.objective}))if(value&&!form.elements[name].value.trim()){form.elements[name].value=value;inferredUploadValues[name]=value;}
  document.getElementById('upload-analysis').innerHTML=`<div class="source-success" role="status">✓ Source processing complete. Your summaries and preparation brief are ready to review.</div><section class="card"><h3>Package interpretation</h3><p>${esc(c.summary)}</p>${result.documents.some(d=>d.analysis.limitations?.length)?'<p class="alert-box">Some documents have extraction limitations. Expand their summaries below to inspect missing or unverified information.</p>':''}<p class="note-sm">${result.cache?.documentHits||0} document analyses reused · ${result.cache?.documentMisses||0} newly analyzed${result.caseCacheHit?' · case interpretation reused':''}</p>${result.documents.map(doc=>`<details><summary>${esc(sources.find(s=>s.id===doc.sourceId)?.title)} · ${esc(doc.analysis.document_type)}</summary><p>${esc(doc.analysis.summary)}</p>${doc.analysis.limitations?.length?`<div class="alert-box">${list(doc.analysis.limitations,'')}</div>`:''}<p>${doc.analysis.tags.map(tag=>badge(tag)).join(' ')}</p><p class="note-sm">${doc.analysis.claims.length} source-linked claims · ${doc.analysis.arguments.length} attributed arguments</p></details>`).join('')}</section>`;
}
function openUploadedPackage(){
  const form=document.getElementById('pdf-package-form'),sources=uploadSources(),c=uploadAnalysis?.caseAnalysis;
  if(!sources.length)throw new Error('Upload at least one readable document.');
  if(sources.reduce((n,s)=>n+s.text.length,0)>2000000)throw new Error('Remove documents to keep extracted text under 2 million characters.');
  const p={schemaVersion:1,id:`document-package-${crypto.randomUUID()}`,title:form.elements.title.value.trim()||'Negotiation package',parties:{us:form.elements.us.value.trim()||'Our side (not inferred)',opponent:form.elements.opponent.value.trim()||'Opponent (not inferred)'},objective:form.elements.objective.value.trim(),walkAway:c?.outside_option||'',sources:sources.map(source=>{const a=uploadAnalysis?.documents.find(d=>d.sourceId===source.id)?.analysis;return {...source,analysis:a?{...a,claims:undefined,claim_ids:a.claims.map(f=>f.id)}:undefined};}),facts:uploadAnalysis?.facts||[],actions:[],strategies:[],variants:[],sourceAnalysis:uploadAnalysis?{caseAnalysis:uploadAnalysis.caseAnalysis,caseCacheHit:uploadAnalysis.caseCacheHit,caseAnalysisKey:uploadAnalysis.caseAnalysisKey,cache:uploadAnalysis.cache,documents:uploadAnalysis.documents.map(({analysis,...metadata})=>metadata)}:null,pipeline:[{status:'complete',detail:`${sources.length} documents read`},{status:uploadAnalysis?'complete':'pending',detail:uploadAnalysis?'Source-linked facts and document analyses extracted by API':'Semantic inference has not run'}]};
  if(p.sourceAnalysis)p.sourceAnalysis.briefContext=JSON.stringify(PrepWorkflow.context(p));
  M.validate(p);if(uploadAnalysis)inferenceNotice={packageId:p.id,status:'complete'};document.getElementById('pdf-dialog').close();pdfBatch=[];uploadAnalysis=null;inferredUploadValues={};receive(p);
}
function bindPdfUpload(){
  const dialog=document.getElementById('pdf-dialog');
  document.getElementById('upload-browse-raw').onclick=()=>openRawSources(uploadSources());
  function cancel(){updateRawProcessing('idle');pdfAbort?.abort();pdfBusy=false;pdfBatch=[];uploadAnalysis=null;inferredUploadValues={};document.getElementById('pdf-package-form').reset();pdfResults();dialog.close();}
  document.getElementById('pdf-cancel').onclick=cancel;dialog.addEventListener('cancel',cancel);
  document.querySelectorAll('[data-upload-group]').forEach(button=>button.onclick=()=>document.querySelector(`[data-document-group="${button.dataset.uploadGroup}"]`).click());
  document.querySelectorAll('[data-document-group]').forEach(input=>input.onchange=async event=>{
    const files=[...event.target.files];event.target.value='';if(!files.length||pdfBusy)return;
    const category=input.dataset.documentGroup,problem=document.getElementById('pdf-error');problem.textContent='';
    if(pdfBatch.length+files.length>30||pdfBatch.reduce((n,x)=>n+x.file.size,0)+files.reduce((n,f)=>n+f.size,0)>100*1024*1024){problem.textContent='Choose up to 30 files totaling no more than 100 MB.';return;}
    pdfAbort?.abort();const controller=new AbortController();pdfAbort=controller;pdfBusy=true;invalidateUploadAnalysis();pdfResults();
    try{
      const {readDocument}=await import('./document-reader.mjs');
      for(const file of files){
        if(controller.signal.aborted)return;
        const item={file,category,status:'Reading…'};pdfBatch.push(item);pdfResults();
        try{
          if(file.size>20*1024*1024)throw new Error('File exceeds 20 MB.');
          if(!/\.(pdf|docx)$/i.test(file.name))throw new Error('Choose PDF or DOCX; save legacy .doc as .docx first.');
          item.hash=[...new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))].map(b=>b.toString(16).padStart(2,'0')).join('');
          const duplicate=pdfBatch.find(x=>x!==item&&x.hash===item.hash&&x.result);
          if(duplicate){duplicate.category=category;pdfBatch.splice(pdfBatch.indexOf(item),1);continue;}
          item.result=await readDocument(file,{signal:controller.signal,onProgress:(page,total)=>{item.status=`Reading page ${page} of ${total}…`;pdfResults();}});
          item.status=`${item.result.format==='docx'?item.result.sections.length+' text sections':item.result.pages.length+' pages'} read${item.result.emptyPages.length?` · pages ${item.result.emptyPages.join(', ')} have no text; OCR may be needed`:''}`;
        }catch(error){if(controller.signal.aborted)return;item.status=`Could not read: ${error.message}`;}
        pdfResults();
      }
      if(uploadSources().reduce((n,s)=>n+s.text.length,0)>2000000)problem.textContent='Combined extracted text exceeds 2 million characters. Remove documents before continuing.';
    }catch(error){problem.textContent=error.message;}finally{if(pdfAbort===controller){pdfBusy=false;pdfResults();}}
  });
  document.getElementById('sources-only').onclick=()=>{try{openUploadedPackage();}catch(error){document.getElementById('pdf-error').textContent=error.message;}};
  document.getElementById('pdf-package-form').onsubmit=async event=>{
    event.preventDefault();if(pdfBusy)return;
    const problem=document.getElementById('pdf-error');problem.textContent='';
    if(uploadAnalysis){try{openUploadedPackage();}catch(error){problem.textContent=error.message;}return;}
    if(uploadSources().reduce((n,s)=>n+s.text.length,0)>2000000){problem.textContent='Remove documents to keep extracted text under 2 million characters.';return;}
    const controller=new AbortController();pdfAbort=controller;pdfBusy=true;updateRawProcessing('running');pdfReady();uploadProgress={};document.getElementById('upload-analysis').innerHTML=inferenceProgressMarkup(uploadSources(),uploadProgress);
    try{await analyzeUploadedSources(controller.signal);}catch(error){updateRawProcessing('failed');if(error.name!=='AbortError')problem.textContent=error.message;if(pdfAbort===controller){stopInferenceProgress(uploadProgress);document.getElementById('upload-analysis').innerHTML=inferenceProgressMarkup(uploadSources(),uploadProgress);}}finally{if(pdfAbort===controller){pdfBusy=false;pdfResults();}}
  };
  pdfResults();
}
