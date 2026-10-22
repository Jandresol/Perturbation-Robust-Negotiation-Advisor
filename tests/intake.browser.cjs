const {chromium}=require('playwright');const assert=require('node:assert/strict');const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8000');
 assert.equal((await page.request.get('http://127.0.0.1:8000/.env')).status(),404);
 assert.equal((await page.request.get('http://127.0.0.1:8000/.data/analysis.sqlite')).status(),404);
 let requests=0;
 await page.route('**/api/sources/parse',async route=>{
   requests++;const p=route.request().postDataJSON().package;
   assert.equal(p.sources.length,3);assert.deepEqual(p.sources.map(s=>s.category),['shared','specific','role_card']);
   assert.deepEqual(p.sources.map(s=>s.visibility),['shared','private','private']);
   const documents=p.sources.map((s,i)=>({sourceId:s.id,cacheHit:false,analysis:{document_type:i===2?'role_card':'report',summary:'Summary of supplied source.',tags:['schedule'],entities:[],represented_side:i===2?'Team A':null,claims:[{id:`f${i}`,sourceId:s.id,text:s.text,quote:s.text,attribution:'source',modality:'asserted',category:'context',conditions:[]}],arguments:[{speaker:'source',position:'Supported position',kind:'attributed_position',premise_fact_ids:[`f${i}`]}],limitations:[]}}));
   await route.fulfill({json:{packageId:'intake',documents,facts:documents.flatMap(d=>d.analysis.claims),caseAnalysis:{title:'Inferred agreement',summary:'Case summary from the sources.',our_side:'Team A',opponent:'Team B',objective:'Agree on a schedule.',outside_option:null,red_lines:[],issues:[]},cache:{documentHits:0,documentMisses:3},caseCacheHit:false}});
 });
 await page.getByRole('button',{name:'Upload source package',exact:true}).click();
 assert.equal(await page.locator('[name=us]').inputValue(),'');
 assert.equal(await page.locator('.inferred-fields').isVisible(),false);
 await page.locator('#pdf-files').setInputFiles(path.resolve('tests/fixtures/shared-brief.pdf'));
 await page.waitForFunction(()=>!document.getElementById('pdf-create').disabled);
 await page.locator('#specific-files').setInputFiles(path.resolve('tests/fixtures/role-card.pdf'));
 await page.waitForFunction(()=>!document.querySelector('[data-upload-group="role_card"]').disabled);
 await page.locator('#role_card-files').setInputFiles(path.resolve('tests/fixtures/role-brief.docx'));
 await page.waitForFunction(()=>!document.getElementById('pdf-create').disabled);
 assert.equal(await page.locator('[data-pdf-role]').count(),0);
 await page.getByRole('button',{name:'Continue & infer',exact:true}).click();
 await page.getByRole('button',{name:'Open preparation',exact:true}).waitFor();
 assert.equal(await page.locator('.inferred-fields').isVisible(),true);
 assert.equal(await page.locator('[name=us]').inputValue(),'Team A');assert.equal(await page.locator('[name=opponent]').inputValue(),'Team B');
 await page.locator('[name=us]').fill('Our chosen label');
 await page.getByRole('button',{name:'Open preparation',exact:true}).click();
 const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')));
 assert.equal(saved.package.parties.us,'Our chosen label');assert.equal(saved.package.title,'Inferred agreement');assert.equal(saved.package.facts.length,3);assert.equal(requests,1);
 await page.getByText('Case background',{exact:true}).click();
 assert.match(await page.locator('main').innerText(),/Case summary from the sources/);
 await page.getByRole('button',{name:'Sources',exact:true}).click();assert.match(await page.locator('.reader-main').innerText(),/Summary of supplied source/);
 for(const width of [1440,768,390]){await page.setViewportSize({width,height:900});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);}
 // A sources-only workspace can run inference later without re-uploading.
 await page.evaluate(()=>{const saved=JSON.parse(localStorage.getItem('negotiation-workspace-v1'));saved.package.sourceAnalysis=null;saved.package.facts=[];saved.package.title='Negotiation package';saved.package.parties={us:'Our side (not inferred)',opponent:'Opponent (not inferred)'};saved.package.objective='';for(const source of saved.package.sources)delete source.analysis;localStorage.setItem('negotiation-workspace-v1',JSON.stringify(saved));});
 await page.reload();
 await page.getByRole('button',{name:'Infer uploaded documents',exact:true}).click();
 await page.waitForFunction(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.sourceAnalysis?.caseAnalysis);
 const inferred=await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package);
 assert.equal(inferred.parties.us,'Team A');assert.equal(inferred.facts.length,3);assert.equal(requests,2);
 assert.deepEqual(errors,[]);await browser.close();console.log('PASS: upload-first optional buckets, one API analysis, inferred editable roles, summaries/tags/arguments, safe secret paths, mobile layout');
})().catch(e=>{console.error(e);process.exit(1)});
