/* No-network reference engines for integration rehearsals, not inferred human utilities. */
(function(root){
 function build(p){
  if(!p.facts?.length)throw new Error('Infer source-linked claims before building the local reference game.');
  const confirmed=p.caseEdits?.redLines?.filter(r=>r.status==='confirmed')||[];
  const excluded=new Set(confirmed.flatMap(r=>r.factIds));
  const ranked=p.facts.filter(f=>!excluded.has(f.id)&&!['constraint','condition'].includes(f.category)).sort((a,b)=>Number(b.category==='commitment')-Number(a.category==='commitment'));
  const topics=ranked.slice(0,3);
  if(!topics.length)throw new Error('No suitable discussion topics remain. Review source claims or connect the peer game builder.');
  const actions=topics.flatMap(f=>['us','opponent'].map(owner=>({id:`reference-${owner}-${f.id}`,owner,label:`Confirm our understanding of: ${f.text}`,factId:f.id,referenceOnly:true})));
  const goals=topics.flatMap((f,i)=>{const [a,b]=actions.slice(i*2,i*2+2);return [
   {id:`reference-cost-us-${i}`,type:'all',actionIds:[a.id],usValue:-1,opponentValue:0},
   {id:`reference-cost-opponent-${i}`,type:'all',actionIds:[b.id],usValue:0,opponentValue:-1},
   {id:`reference-joint-${i}`,type:'all',actionIds:[a.id,b.id],usValue:3,opponentValue:3}
  ];});
  for(const action of actions){const edit=p.referenceGameEdits?.actions?.[action.id];if(edit){if(!['us','opponent'].includes(edit.owner)||typeof edit.label!=='string'||!edit.label.trim())throw new Error('Each reference action needs a label and valid owner.');Object.assign(action,edit);}}
  for(const goal of goals){const edit=p.referenceGameEdits?.goals?.[goal.id];if(edit){if(!Number.isFinite(edit.usValue)||!Number.isFinite(edit.opponentValue))throw new Error('Reference utility values must be finite.');Object.assign(goal,edit);}}
  const assumptions=['REFERENCE GAME: actions are reciprocal confirmations of source interpretations, not inferred real-world concessions.','Utility values are illustrative process weights: each confirmation costs its owner 1; joint confirmation benefits each side by 3.','Textual red lines are displayed for human review; source-topic exclusion does not encode every real-world implication.','This engine cannot infer the full negotiation, real utility, feasibility, or stakeholder impact.'];
  return {packageId:p.id,actions,game:{method:'local-reference-v1',referenceOnly:true,goals,maxOffers:2,maxActionsPerSide:2,forbiddenActions:(p.referenceGameEdits?.forbiddenActions||[]).filter(id=>actions.some(a=>a.id===id)),assumptions,opponentReadings:[{id:'lower-joint-benefit',values:Object.fromEntries(goals.map(g=>[g.id,g.id.includes('joint')?2:g.opponentValue]))}]}};
 }
 function signatures(p){const result=LocalPlanner.planPackage(p);return {game:JSON.stringify({actions:p.actions.map(a=>[a.id,a.owner,a.factId]),goals:p.game.goals,forbiddenActions:p.game.forbiddenActions,opponentReadings:p.game.opponentReadings}),plans:JSON.stringify(result.strategies.map(s=>s.steps))};}
 function perturb(p){
  if(!p.game?.referenceOnly)throw new Error('The built-in perturbation engine compares only the built-in reference game. Use your peer engine for another game model.');
  const baseline=signatures(p),variants=[],target=128,seen=new Set();
  const baselineOpening=LocalPlanner.planPackage(p).strategies[0]?.opening||'No improving offer under these assumptions.';
  const replacements=[
   [/\bprior to\b/i,['before','ahead of']], [/\bin order to\b/i,['to','so as to']],
   [/\bdue to\b/i,['because of','owing to','as a result of']], [/\brather than\b/i,['instead of','as opposed to']],
   [/\bat present\b/i,['currently','at this time']], [/\bcurrently\b/i,['at present','at this time']],
   [/\bapproximately\b/i,['about','roughly','around']], [/\bmore than\b/i,['over','in excess of']],
   [/\bat least\b/i,['a minimum of']], [/\bat most\b/i,['a maximum of']],
   [/\bhowever\b/i,['nevertheless','nonetheless']], [/\bquickly\b/i,['rapidly','swiftly']],
   [/\brapidly\b/i,['quickly','swiftly']], [/\bimmediately\b/i,['without delay']],
   [/\bfood aid\b/i,['food assistance']], [/\bfood assistance\b/i,['food aid']],
   [/\bfood distribution\b/i,['distribution of food']], [/\bdistribution of food\b/i,['food distribution']],
   [/\bfunding constraints\b/i,['funding limitations']], [/\bfunding shortages\b/i,['shortfalls in funding']],
   [/\bfinancial resources\b/i,['funds']], [/\bwith respect to\b/i,['regarding','concerning','in relation to']],
   [/\bregarding the\b/i,['concerning the','in relation to the']], [/\bconcerns about\b/i,['concerns regarding']],
   [/\bconcerns over\b/i,['concerns about']], [/\bconcerned that\b/i,['worried that']],
   [/\bwishes to\b/i,['would like to']], [/\bseeks to\b/i,['aims to']], [/\baims to\b/i,['seeks to']],
   [/\bplans to\b/i,['intends to']], [/\btogether with\b/i,['along with']],
   [/\bin addition\b/i,['additionally']], [/\bat the same time\b/i,['simultaneously']],
   [/\bensure that\b/i,['make sure that']], [/\bprior agreement\b/i,['advance agreement']],
   [/\bbefore the\b/i,['prior to the']], [/\bafter the\b/i,['following the']],
   [/\bsufficient for\b/i,['enough for']], [/\bprovide assistance\b/i,['provide support']],
   [/\bassist with\b/i,['help with','assist in']], [/\bto assist\b/i,['to help']],
   [/\bfood supplies\b/i,['supplies of food']], [/\blocal community members\b/i,['members of the local community']],
   [/\brefugee camp\b/i,['camp for refugees']],
   [/\band\b/i,['as well as']], [/\bsuch as\b/i,['including']], [/\bincluding\b/i,['such as']]
  ];
  const names=[...new Set([p.parties?.us,p.parties?.opponent,...p.sources.flatMap(s=>(s.analysis?.entities||[]).map(e=>e.name))].filter(x=>typeof x==='string'&&x.length>=3))];
  const preservesNames=(original,text)=>names.every(name=>!original.includes(name)||text.includes(name));
  const protectedTokens=t=>(t.match(/\d+(?:[.,]\d+)*|\b(?:not|never|no|must|cannot|may|should|requires?|refuses?)\b/gi)||[]).map(x=>x.toLowerCase()).sort().join('|');
  function append(fact,text,frame){
   const key=fact.id+'|'+text;if(seen.has(key)||variants.length>=target)return;seen.add(key);
   const next=structuredClone(p);next.facts.find(f=>f.id===fact.id).text=text;
   const built=build(next);next.actions=built.actions;next.game=built.game;
   const scored=signatures(next),same=scored.game===baseline.game&&scored.plans===baseline.plans;
   variants.push({id:`reference-reading-${String(variants.length+1).padStart(3,'0')}`,factId:fact.id,text,frame,comparisonCompleted:true,outcome:same?'stable':'changed',method:'local-reference-v1',baselineNextMove:baselineOpening,nextMove:LocalPlanner.planPackage(next).strategies[0]?.opening||'No improving offer under these assumptions.',gameUnchanged:scored.game===baseline.game,planUnchanged:scored.plans===baseline.plans,validation:'Rule-based wording candidate; numbers, known entity names, and listed modal/negation tokens unchanged. Bidirectional entailment and human semantic audit have not been performed.',effect:`${same?'Same':'Different'} canonical reference game and planner sequence. The reference builder uses fixed claim categories and IDs; this is a pipeline comparison, not evidence of robust semantic inference.`});
  }
  // Breadth-first combinations change wording only. No presentation fillers or duplicate originals.
  const visited=new Map(p.facts.map(f=>[f.id,new Set([f.text])]));
  let frontier=p.facts.map(fact=>({fact,text:fact.text,depth:0}));
  for(let depth=0;depth<4&&variants.length<target;depth++){
   const next=[];
   for(const state of frontier){
    for(const [pattern,choices] of replacements){
     if(!pattern.test(state.text))continue;
     for(const choice of choices){
      const text=state.text.replace(pattern,choice);
      if(visited.get(state.fact.id).has(text)||protectedTokens(text)!==protectedTokens(state.fact.text)||!preservesNames(state.fact.text,text))continue;
      visited.get(state.fact.id).add(text);
      append(state.fact,text,depth?'Combined phrase substitutions':'Phrase substitution');
      next.push({fact:state.fact,text,depth:depth+1});
      if(variants.length>=target)break;
     }
     if(variants.length>=target)break;
    }
    if(variants.length>=target)break;
   }
   frontier=next;
  }
  return {packageId:p.id,variants,referenceOnly:true,generation:{target,generated:variants.length,shortfall:target-variants.length,method:'bounded-wording-substitutions'},release:{sourceSupport:false,feasibility:false,ethicsReviewed:false,freshRescored:false}};
 }
 const api={build,perturb};if(typeof module!=='undefined'){globalThis.LocalPlanner=require('./planner');module.exports=api;}else root.ReferenceEngines=api;
})(typeof window!=='undefined'?window:globalThis);
