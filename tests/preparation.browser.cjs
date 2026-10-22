const {chromium}=require('playwright');const assert=require('node:assert/strict');const path=require('node:path');
(async()=>{
const browser=await chromium.launch({executablePath:process.env.CHROME_PATH||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto('http://127.0.0.1:8000');
// Configure the package-to-game service before upload. No manually reviewed facts exist.
await page.evaluate(()=>localStorage.setItem('negotiation-engine-connections-v1',JSON.stringify({game:'http://127.0.0.1:8000/test-game',perturbation:'http://127.0.0.1:8000/test-reword'})));
let calls=0;
await page.route('**/test-game',async route=>{
 const payload=route.request().postDataJSON();assert.equal(payload.package.facts.length,0);calls++;
 const s=payload.package.sources[0],quote=s.pages[0].text;
 await route.fulfill({json:{packageId:payload.packageId,facts:[{id:'f1',sourceId:s.id,page:1,text:quote,quote}],actions:[{id:'a1',owner:'us',label:'Agree on schedule',factId:'f1'}],game:{goals:[{id:'g1',type:'all',actionIds:['a1'],usValue:2,opponentValue:1}]}}});
});
await page.route('**/test-reword',async route=>{const payload=route.request().postDataJSON();assert.equal(payload.package.facts.length,1);assert.equal(payload.factSetFrozen,true);await route.fulfill({status:503,body:'Unavailable'});});
await page.getByRole('button',{name:'Upload source package',exact:true}).click();
await page.locator('#pdf-files').setInputFiles(['shared-brief.pdf','role-card.pdf'].map(f=>path.resolve('tests/fixtures',f)));
await page.waitForFunction(()=>!document.querySelector('#pdf-create').disabled);

await page.getByRole('button',{name:'Continue with sources',exact:true}).click();
await page.waitForFunction(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.preparation.run?.status==='complete');
assert.equal(calls,1);
const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')));
assert.equal(saved.package.preparation.baseline.facts.length,1);assert.ok(saved.package.strategies.length);assert.equal(saved.package.pipeline[3].status,'failed');
assert.equal(await page.getByRole('button',{name:'Accept claim',exact:true}).count(),0);
assert.doesNotMatch(await page.locator('main').innerText(),/awaiting review|Review claims|Accept or correct source-linked/);
assert.equal(await page.getByRole('heading',{name:'Your preparation brief',exact:true}).count(),1);
await page.locator('[data-prep-tab=documents]').click();await page.locator('#document-search').fill('schedule');
assert.match(await page.locator('#document-search-results').innerText(),/shared-brief.pdf/);
await page.locator('[data-hit-source]').click();assert.match(await page.locator('#document-text mark').innerText(),/schedule/);
await page.locator('[data-prep-tab=overview]').click();await page.getByRole('button',{name:'Edit team brief',exact:true}).click();
await page.locator('[name=opening]').fill('Team-selected opening');await page.locator('[name=fallback]').fill('Team-selected fallback');await page.getByRole('button',{name:'Save team brief',exact:true}).click();
await page.reload();assert.match(await page.locator('main').innerText(),/Team-selected opening/);
for(const width of [1440,768,390]){await page.setViewportSize({width,height:900});for(const tab of ['overview','documents','issues','engines']){await page.locator(`[data-prep-tab=${tab}]`).click();assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${tab} overflows ${width}`);}}
// Saved workspaces with thousands of pending sentence suggestions no longer get review tasks.
await page.evaluate(()=>{const key='negotiation-workspace-v1',s=JSON.parse(localStorage.getItem(key)),c=s.package.preparation.candidates[0];s.package.preparation.candidates=Array.from({length:1128},(_,i)=>({...c,id:`legacy-${i}`,status:'pending'}));s.package.pipeline[1]={status:'running',detail:'1128 awaiting review'};localStorage.setItem(key,JSON.stringify(s));});
await page.reload();assert.doesNotMatch(await page.locator('main').innerText(),/1128|awaiting review|Review claims/);
// Stop an overrun at the generation cutoff; late responses must not replace the baseline.
await page.clock.install();
await page.unroute('**/test-game');await page.unroute('**/test-reword');
await page.route('**/test-game',async route=>{const request=route.request().postDataJSON();const b=request.package;await route.fulfill({json:{packageId:request.packageId,facts:b.facts,actions:b.actions,game:b.game}});});
let heldRoute,releaseHeld;
await page.route('**/test-reword',route=>{heldRoute=route;return new Promise(resolve=>{releaseHeld=resolve;});});
await page.getByRole('button',{name:'Build strategy options',exact:true}).click();
await page.waitForFunction(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.pipeline[3]?.status==='running');
await page.clock.fastForward(300000);
await page.waitForFunction(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.preparation.run.status==='finalized');
const frozen=await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.strategies);
try{await heldRoute.fulfill({json:{packageId:saved.package.id,variants:[]}});}catch{}finally{releaseHeld();}
assert.deepEqual(await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.strategies),frozen);
assert.deepEqual(errors,[]);await browser.close();console.log('PASS: automatic PDF → inference with zero fact approvals → planner → brief; failed rewording preserves baseline; migration; cutoff/late-response protection; 12 responsive checks');
})().catch(e=>{console.error(e);process.exit(1)});
