const {chromium}=require('playwright');const assert=require('node:assert/strict');const fixture=require('../example-package.json');
(async()=>{const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});try{
 const page=await browser.newPage(),errors=[];let apiCalls=0;page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/sources/parse'))apiCalls++;});
 await page.goto('http://127.0.0.1:8000');
 const p=structuredClone(fixture);p.objective='Agree on workshop scope and dates.';
 const session={packageId:p.id,mode:'source-rehearsal',events:[],commitments:[],elapsed:0,duration:900,running:false,ended:false};
 await page.evaluate(data=>localStorage.setItem('negotiation-workspace-v1',JSON.stringify(data)),{package:p,session,selected:null,view:'classroom'});await page.reload();
 await page.waitForFunction(()=>LiveStrategy.status==='ready');await page.locator('[data-guidance-section=responses] > summary').click();assert.ok((await page.locator('.strategy-guidance').innerText()).includes('Questions to test'));
 const field=page.locator('#event-form [name=text]');await field.fill('We seek agreement on workshop dates.');await page.getByRole('button',{name:'Review event',exact:true}).click();await page.getByRole('button',{name:'Confirm event',exact:true}).click();await page.waitForFunction(()=>LiveStrategy.current?.events===1);
 assert.match(await page.locator('.strategy-guidance').innerText(),/deadline, and the person who can approve/);
 const rescored=await page.evaluate(async()=>{const p=structuredClone(state.package);p.game={maxOffers:2,maxActionsPerSide:1,goals:[{id:'cost',actionIds:[p.actions[0].id],type:'all',usValue:-2,opponentValue:4},{id:'benefit',actionIds:[p.actions[1].id],type:'all',usValue:5,opponentValue:-1}]};return await new Promise((resolve,reject)=>{const w=new Worker('live-strategy-worker.js');const timer=setTimeout(()=>{w.terminate();reject(Error('Worker timeout'));},3000);w.onmessage=e=>{clearTimeout(timer);w.terminate();resolve(e.data);};w.onerror=e=>reject(Error(e.message));w.postMessage({package:p,session:state.session,brief:PrepWorkflow.draftBrief(p)});});});
 assert.match(rescored.planningStatus,/re-scored/);assert.ok(rescored.options.length);
 // A slow worker must time out without rerendering or erasing an in-progress exchange.
 await page.route('**/live-strategy-worker.js*',r=>r.fulfill({contentType:'text/javascript',body:'self.onmessage=()=>{};'}));
 await field.fill('Another confirmed exchange.');await page.getByRole('button',{name:'Review event',exact:true}).click();await page.getByRole('button',{name:'Confirm event',exact:true}).click();
 await field.fill('Keep this draft while guidance is working.');await page.evaluate(()=>window.originalEventForm=document.getElementById('event-form'));
 await page.waitForFunction(()=>LiveStrategy.status==='limited');assert.equal(await field.inputValue(),'Keep this draft while guidance is working.');assert.equal(await page.evaluate(()=>originalEventForm===document.getElementById('event-form')),true);assert.equal(await field.isEditable(),true);
 assert.equal(apiCalls,0);assert.deepEqual(errors,[]);console.log('PASS: source-specific background guidance; confirmed-turn refresh; worker timeout retains form and draft; no paid API calls');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
