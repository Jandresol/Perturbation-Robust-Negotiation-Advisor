/* Original rendered benchmark artifacts from the teammate perturbation branch. */
let benchmarkRun='sim1';
const benchmarkPlots=[
 ['acceptance','Acceptance rate','Share of candidates accepted at each requested rewording strength.'],
 ['distance','Embedding distance','Distances for accepted and rejected candidates by operator and requested strength.'],
 ['nli','Two-way entailment','Forward and backward entailment scores; dashed lines mark the plotted filter threshold.'],
 ['rejections','Acceptance & rejection reasons','Candidate counts and rejection reasons for each operator.'],
 ['noise_match','Matched noise control','Embedding distance of accepted wordings compared with their matched noise controls.'],
 ['sentence_pairs','Original & reworded examples','Recorded sentence pairs with cosine and entailment scores from the original benchmark run.']
];
function benchmarkFigures(){
 const base=`results/perturbation/${benchmarkRun}`;
 return `<section class="card benchmark-gallery" aria-label="Benchmark visualizations"><div class="benchmark-heading"><div><p class="eyebrow">TEAMMATE BENCHMARK RESULTS</p><h2>Rewording engine visualizations</h2><p class="note-sm">Saved figures from the perturbation branch. These describe the selected benchmark run, not the uploaded case or its current strategy scores.</p></div><label>Benchmark run<select id="benchmark-run"><option value="sim1" ${benchmarkRun==='sim1'?'selected':''}>Run 1 · sim1</option><option value="sim2" ${benchmarkRun==='sim2'?'selected':''}>Run 2 · sim2</option></select></label></div><div class="action-group"><a class="btn" href="${base}/benchmark.csv" download>Download benchmark CSV</a><details><summary>Figure provenance</summary><p class="note-sm">Imported unchanged from <code>setup/perturbation-engine-scaffold</code>. Original figure labels, thresholds, and decisions are retained; historical filter output is not reinterpreted as a result for the current case.</p></details></div><div class="benchmark-grid">${benchmarkPlots.map(([id,title,caption])=>`<figure class="benchmark-figure"><h3>${title}</h3><button type="button" class="benchmark-preview" data-benchmark-plot="${id}" aria-label="Enlarge ${title}"><img src="${base}/${id}.png" alt="${title} — benchmark ${benchmarkRun}" loading="lazy"></button><figcaption>${caption}</figcaption><div class="action-group"><button type="button" class="btn-ghost-link" data-benchmark-plot="${id}">Enlarge</button><a class="btn-ghost-link" href="${base}/${id}.pdf" download>Download PDF</a></div></figure>`).join('')}</div></section>`;
}
function bindResearchFigures(){
 loadCurrentCaseFigures();
 const select=document.getElementById('benchmark-run');
 if(select)select.onchange=e=>{benchmarkRun=e.target.value==='sim2'?'sim2':'sim1';document.querySelector('.benchmark-gallery').outerHTML=benchmarkFigures();bindResearchFigures();document.getElementById('benchmark-run').focus();};
 document.querySelectorAll('[data-benchmark-plot]').forEach(el=>el.onclick=()=>{
  const plot=benchmarkPlots.find(([id])=>id===el.dataset.benchmarkPlot);if(!plot)return;
  const [id,title,caption]=plot,base=`results/perturbation/${benchmarkRun}`;
  let dialog=document.getElementById('benchmark-figure-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='benchmark-figure-dialog';document.body.append(dialog);}
  dialog.innerHTML=`<div class="row-actions"><h2>${title} · ${benchmarkRun}</h2><button type="button" class="btn" id="benchmark-close">Close figure</button></div><p>${caption}</p><div class="action-group"><a class="btn" href="${base}/${id}.pdf" download>Download PDF</a><a class="btn" href="${base}/${id}.png" download>Download PNG</a></div><div class="benchmark-full-image"><img src="${base}/${id}.png" alt="${title} — benchmark ${benchmarkRun}"></div>`;
  document.getElementById('benchmark-close').onclick=()=>dialog.close();dialog.showModal();
 });
}

/* Active-case charts use saved semantic measurements only; rendering makes no API calls. */
function researchMeasurements(p){
 return (p.variants||[]).flatMap(v=>{let m=v.audit||v.validation;try{if(typeof m==='string')m=JSON.parse(m);}catch{return [];}if(!m||typeof m.accepted!=='boolean')return [];
 return [{...m,id:v.id,factId:v.factId,text:v.text,original:(p.facts||[]).find(f=>f.id===v.factId)?.text||'Original claim unavailable',group:`${m.operator||v.method||'Semantic rewording'} · ${m.level||v.frame||'Unspecified strength'}`}];});
}

const caseFigureRequests=new Map();
function currentCaseFigures(p){
 const rows=researchMeasurements(p);
 return `<section class="card case-research-gallery"><p class="eyebrow">UPLOADED CASE RESULTS</p><h2>Wording test visualizations</h2><p>${esc(p.title||'Current case')} · ${rows.length} measured candidates · ${rows.filter(r=>r.accepted).length} accepted by the semantic filter</p><p class="note-sm">Python figures from saved case measurements. No model calls.</p><div id="current-case-figure-output" aria-live="polite">${rows.length?'<p>Rendering figures…</p>':'<p>Charts populate when the background wording tests finish. Track progress at the top of this page.</p>'}</div></section><details class="historical-chart-examples"><summary>Example figures from teammates’ benchmark runs</summary>${benchmarkFigures()}</details>`;
}
async function loadCurrentCaseFigures(){
 const node=document.getElementById('current-case-figure-output'),p=state.package;if(!node||!researchMeasurements(p).length)return;
 const payload={title:p.title,variants:p.variants,facts:p.facts.map(f=>({id:f.id,text:f.text,sourceId:f.sourceId})),sources:p.sources.map(s=>({id:s.id,title:s.title}))},key=JSON.stringify(payload);
 if(!caseFigureRequests.has(key))caseFigureRequests.set(key,fetch('/api/engines/figures',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({package:payload})}).then(async r=>{const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not render figures.');return data;}));
 try{
  const manifest=await caseFigureRequests.get(key);if(!node.isConnected)return;
  node.innerHTML=`<a class="btn" href="${manifest.csv}" download="case-measurements.csv">Download measurements CSV</a><div class="case-python-grid">${benchmarkPlots.map(([id,title,caption])=>`<figure class="benchmark-figure"><h3>${title}</h3><button type="button" class="benchmark-preview" data-case-plot="${id}" aria-label="Enlarge current case ${title}"><img src="${manifest.plots[id].png}" alt="${esc(title)} — current case" loading="lazy"></button><figcaption>${esc(id==='sentence_pairs'?'Original and reworded passages from this case, with recorded cosine and entailment scores.':id==='nli'?'Forward and backward entailment by operator. Threshold lines appear only when recorded in the saved run.':caption)}</figcaption><div class="action-group"><button type="button" class="btn-ghost-link" data-case-plot="${id}">Enlarge</button><a class="btn-ghost-link" href="${manifest.plots[id].pdf}" download="${id}.pdf">Download PDF</a><a class="btn-ghost-link" href="${manifest.plots[id].png}" download="${id}.png">Download PNG</a></div></figure>`).join('')}</div>`;
  node.querySelectorAll('[data-case-plot]').forEach(button=>button.onclick=()=>{
   const id=button.dataset.casePlot,title=benchmarkPlots.find(p=>p[0]===id)[1];let dialog=document.getElementById('case-figure-dialog');if(!dialog){dialog=document.createElement('dialog');dialog.id='case-figure-dialog';document.body.append(dialog);}
   dialog.innerHTML=`<div class="row-actions"><h2>${esc(title)}</h2><button type="button" class="btn" id="case-figure-close">Close figure</button></div><a class="btn" href="${manifest.plots[id].pdf}" download="${id}.pdf">Download PDF</a><img src="${manifest.plots[id].png}" alt="${esc(title)}">`;
   document.getElementById('case-figure-close').onclick=()=>dialog.close();dialog.showModal();
  });
 }catch(error){if(!node.isConnected)return;node.innerHTML=`<p>Figures could not render: ${esc(error.message)}</p><button type="button" class="btn" id="retry-case-figures">Retry figure rendering</button>`;document.getElementById('retry-case-figures').onclick=()=>{caseFigureRequests.delete(key);loadCurrentCaseFigures();};}
}
