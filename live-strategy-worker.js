/* Bounded local decision support. Confirmed events only; no network or commitments. */
self.onmessage=({data})=>{
 const {package:p,session:s,brief:b}=data,last=s.events.at(-1);
 const words=text=>new Set((text.toLowerCase().match(/[a-z]{4,}/g)||[]).filter(x=>!['that','with','this','from','have','their','they','your','what','should'].includes(x)));
 const terms=words([b.objective,last?.text||''].join(' '));
 const facts=p.facts.filter(f=>{const source=p.sources.find(s=>s.id===f.sourceId);return source&&source.visibility!=='private'&&!['role_card','specific'].includes(source.category);}).map(f=>({f,score:[...words(f.text)].filter(x=>terms.has(x)).length+(['constraint','condition','goal','commitment'].includes(f.category)?2:0)})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,3).map(x=>x.f);
 const asks=facts.map(f=>({text:`Ask ${p.parties.opponent}: “Regarding ${f.text.replace(/[.!?]+$/,'')}, what specific step can your side authorize, by when, and how would we verify it?”`,factId:f.id}));
 const open=s.events.filter(e=>e.type==='offer'&&e.speaker==='opponent'&&!s.events.some(r=>['accept','reject'].includes(r.type)&&r.offerId===e.id)).at(-1);
 let next=last?`Turn the discussion into an actionable proposal: ask ${p.parties.opponent} to name one concrete step toward “${b.objective}”, its deadline, and the person who can approve it.`:b.opening||`Explain the outcome you seek: ${b.objective}`;
 if(last?.speaker==='opponent'&&last.type==='question')next=`Answer the question they raised: “${last.text}”. Separate what your side can authorize from what needs approval; tie your answer to ${b.objective}`;
 if(open)next=`Clarify this offer before deciding: “${open.text}”. Ask which terms are conditional, who delivers each step, and when. Check the full package against your red lines.`;
 if(last?.type==='reject')next=`Ask what specifically prevented agreement: “${last.text}”. Test this fallback: ${b.fallback||'ask which term could change without crossing either side’s limits.'}`;
 if(last?.type==='accept')next='Restate the accepted terms and ask each side to confirm its owner, deadline, and verification method. Do not assume additional promises were accepted.';
 const outside=s.events.some(e=>e.type==='unmodeled');
 if(outside)next='Clarify the new issue and who can authorize it before extending the prepared agreement. Existing scores omit this issue.';
 let options=[],planningStatus='Source-grounded prompts; no scored game available.';
 if(p.game?.referenceOnly)planningStatus='Source-grounded prompts; local simulation scores are illustrative.';
 else if(p.game&&!outside){
  try{importScripts('planner.js');const result=selfPlan(p,s.commitments);options=result;planningStatus='Remaining options re-scored against confirmed commitments.';}catch{planningStatus='Scoring unavailable; prepared guidance remains available.';}
 }
 self.postMessage({next,asks,options,planningStatus,events:s.events.length});
};
// The planner publishes its handler in a worker. Capture it without invoking it on the UI thread.
function selfPlan(p,commitments){let result;const send=self.postMessage;self.postMessage=x=>{result=x;};try{self.onmessage({data:{package:p,commitments}});}finally{self.postMessage=send;}if(!result?.ok)throw Error(result?.error||'No plan');return result.result.strategies||result.result;}
