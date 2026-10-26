/* Read-only extracted text. Browsing never cancels or restarts inference. */
let rawBrowserSources=[],rawBrowserIndex=0,rawBrowserPage=0,rawProcessingStatus='idle';
let inferenceNotice=null;
function rawProcessingNotice(){
 return rawProcessingStatus==='complete'?'<div class="source-success" role="status">✓ Source processing complete. Your summaries and preparation brief are ready to review.</div>':rawProcessingStatus==='running'?'<p role="status">Analysis continues in the background. You can keep reading.</p>':rawProcessingStatus==='failed'?'<p role="status">Analysis needs attention. Extracted source text remains available.</p>':'';
}
function updateRawProcessing(status){rawProcessingStatus=status;const el=document.getElementById('raw-processing-status');if(el)el.innerHTML=rawProcessingNotice();}
function sourceProcessingNotice(){
 if(sourceInferenceBusy)return `<section class="source-processing-banner" role="status"><p>Sources are processing. Browse the extracted text while you wait.</p>${state.view==='sources'?'':'<button type="button" class="btn" data-view="sources">Read sources</button>'}</section>`;
 return inferenceNotice?.packageId===state.package?.id&&inferenceNotice?.status==='complete'?'<div class="source-success" role="status">✓ Source processing complete. Your summaries and preparation brief are ready to review.</div>':'';
}
function openRawSources(sources){
 rawBrowserSources=sources;rawBrowserIndex=0;rawBrowserPage=0;
 let dialog=document.getElementById('raw-source-dialog');
 if(!dialog){dialog=document.createElement('dialog');dialog.id='raw-source-dialog';document.body.append(dialog);}
 drawRawSources();dialog.showModal();
}
function drawRawSources(){
 const dialog=document.getElementById('raw-source-dialog'),source=rawBrowserSources[rawBrowserIndex];
 const pages=source?sourceUnits(source):[],page=pages[rawBrowserPage];
 dialog.innerHTML=`<div class="row-actions"><h2>Raw source text</h2><button type="button" class="btn" id="raw-close">${rawProcessingStatus==='running'?'Back to processing':'Back to brief'}</button></div><p class="note-sm">Extracted text before interpretation. Tables and reading order may differ from the original. Use search to find a phrase in the current document.</p><div id="raw-processing-status">${rawProcessingNotice()}</div><label>Document<select id="raw-source-select">${rawBrowserSources.map((s,i)=>`<option value="${i}" ${i===rawBrowserIndex?'selected':''}>${esc(s.title)}</option>`).join('')}</select></label><label>Find in this document<input type="search" id="raw-search" placeholder="Search extracted text"></label><p id="raw-search-status" role="status"></p><div class="row-actions"><button type="button" class="btn" id="raw-prev" ${!rawBrowserPage?'disabled':''}>Previous</button><label>${source?.format==='docx'?'Section':'Page'}<select id="raw-page-select">${pages.map((p,i)=>`<option value="${i}" ${i===rawBrowserPage?'selected':''}>${esc(p.number)}</option>`).join('')}</select></label><button type="button" class="btn" id="raw-next" ${rawBrowserPage>=pages.length-1?'disabled':''}>Next</button></div><article id="raw-source-text" class="document-page">${esc(page?.text||'No readable text is available yet.')}</article>`;
 document.getElementById('raw-close').onclick=()=>dialog.close();
 document.getElementById('raw-source-select').onchange=e=>{rawBrowserIndex=Number(e.target.value);rawBrowserPage=0;drawRawSources();};
 document.getElementById('raw-page-select').onchange=e=>{rawBrowserPage=Number(e.target.value);drawRawSources();};
 document.getElementById('raw-prev').onclick=()=>{rawBrowserPage--;drawRawSources();};
 document.getElementById('raw-next').onclick=()=>{rawBrowserPage++;drawRawSources();};
 document.getElementById('raw-search').oninput=e=>{
  const q=e.target.value.trim().toLowerCase(),matches=pages.filter(p=>p.text.toLowerCase().includes(q));
  document.getElementById('raw-search-status').textContent=q?`${matches.length} matching ${source?.format==='docx'?'sections':'pages'}`:'';
  document.getElementById('raw-source-text').innerHTML=(q?matches:page?[page]:[]).map(p=>`<h4>${source?.format==='docx'?'Section':'Page'} ${esc(p.number)}</h4><p class="source-text">${esc(p.text)}</p>`).join('');
 };
}
