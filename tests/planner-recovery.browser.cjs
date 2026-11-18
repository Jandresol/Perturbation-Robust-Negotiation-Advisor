const {chromium}=require('playwright');const assert=require('node:assert/strict');const fs=require('node:fs');const fixture=require('../example-package.json');
(async()=>{const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});try{
 const page=await browser.newPage(),errors=[];let paid=0;page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/sources/parse'))paid++;});
 await page.goto('http://127.0.0.1:8000');const p=structuredClone(fixture);p.actions=[];p.strategies=[];p.variants=[];delete p.game;
 await page.evaluate(package=>localStorage.setItem('negotiation-workspace-v1',JSON.stringify({package,selected:null,session:null,view:'prep'})),p);await page.reload();
 let loads=0;const script=fs.readFileSync('planner.js','utf8');await page.route('**/planner.js*',r=>{loads++;return loads===1?r.abort():r.fulfill({contentType:'text/javascript',body:script});});
 await page.locator('#prep-engine > summary').click();await page.getByRole('button',{name:'Build strategy options',exact:true}).click();
 await page.waitForFunction(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')).package.preparation.run?.status==='complete');
 let saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('negotiation-workspace-v1')));assert.ok(saved.package.strategies.length);assert.ok(saved.package.preparation.baseline);assert.equal(loads,2);assert.equal(paid,0);
 // Domain errors should not silently retry or create invented options.
 await page.unroute('**/planner.js*');const invalid=await page.evaluate(async()=>{const p=structuredClone(state.package);p.game.goals=[];try{await runPlannerWorker(p,[]);return '';}catch(e){return e.message;}});assert.match(invalid,/game needs goals/);
 // An unavailable app file should produce an actionable message, not a generic worker error.
 await page.route('**/planner.js*',r=>r.fulfill({status:404,body:'Missing'}));const missing=await page.evaluate(async()=>{try{await runPlannerWorker(state.package,[]);return '';}catch(e){return e.message;}});assert.match(missing,/Planner file is unavailable.*404/);
 assert.deepEqual(errors,[]);console.log('PASS: Build strategy options recovers worker load failure, stores baseline, makes no paid calls; invalid games do not retry; missing file gives actionable error');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
