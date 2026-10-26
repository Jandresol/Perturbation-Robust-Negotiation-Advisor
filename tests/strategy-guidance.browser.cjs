const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fixture=require('../example-package.json');
(async()=>{
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
  const page=await browser.newPage(),errors=[];let calls=0;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().includes('/api/sources/parse'))calls++;});
  await page.goto('http://127.0.0.1:8000');
  const p=structuredClone(fixture);p.preparation={brief:{opening:'Ask about delivery priorities.',fallback:'Explore a smaller first exchange.',redLines:['No unapproved commitments.'],assumptions:[],branches:['If timing blocks agreement, ask which dates work.']}};
  await page.evaluate(package=>{package.preparation={...Preparation.parseSources(package.sources),brief:package.preparation.brief};localStorage.setItem('negotiation-workspace-v1',JSON.stringify({package,selected:null,session:null,view:'prep'}));},p);
  await page.reload();
  if(errors.length)throw new Error(errors.join('; '));
  await page.locator('.strategy-results > summary').click();
  await page.getByRole('button',{name:'Select strategy',exact:true}).first().click();
  await page.getByRole('button',{name:'Start negotiation',exact:true}).click();
  const guidance=page.getByRole('complementary',{name:'Strategy guidance'});
  const nextMove=guidance.locator('.card').first();
  assert.ok((await nextMove.innerText()).includes(p.objective));
  assert.ok((await nextMove.innerText()).includes('Ask about delivery priorities.'));
  assert.doesNotMatch(await nextMove.innerText(),/Open with your objective/);
  for(const text of ['Ask about delivery priorities.','Explore a smaller first exchange.','No unapproved commitments.','If timing blocks agreement, ask which dates work.'])assert.ok((await guidance.innerText()).includes(text));
  await page.locator('#event-form [name=type]').selectOption('unmodeled');
  await page.locator('#event-form [name=text]').fill('A new approval requirement was raised.');
  await page.getByRole('button',{name:'Review event',exact:true}).click();
  assert.doesNotMatch(await guidance.innerText(),/A new issue falls outside|Clarify the new issue/);
  await page.getByRole('button',{name:'Confirm event',exact:true}).click();
  assert.match(await guidance.innerText(),/A new issue falls outside|Clarify the new issue/);
  await page.reload();assert.match(await guidance.innerText(),/A new issue falls outside|Clarify the new issue/);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);}
  assert.equal(calls,0);assert.deepEqual(errors,[]);
  console.log('PASS: team strategy on negotiation page; guidance updates only after confirmation; reload persists; responsive; no inference calls');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
