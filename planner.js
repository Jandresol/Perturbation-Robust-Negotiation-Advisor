/* Deterministic bounded planner for the commitment-game contract. No model calls. */
(function(root){
function planPackage(p, commitments=[]) {
 const actions=p.actions,g=p.game;
 if(!g||!Array.isArray(g.goals)||!g.goals.length||g.goals.length>64)throw new Error('The game needs goals with actionIds, type, usValue, and opponentValue.');
 if(!actions.length||actions.length>12)throw new Error('Local exact planning supports 1–12 actions. Larger games need an external planner.');
 const ids=new Map(actions.map((a,i)=>[a.id,i]));
 const maskOf=arr=>arr.reduce((m,id)=>{if(!ids.has(id))throw new Error(`Unknown game action: ${id}`);return m|(1<<ids.get(id));},0);
 const goals=g.goals.map(goal=>{
  if(typeof goal.id!=='string'||!['linear','all'].includes(goal.type)||!Array.isArray(goal.actionIds)||!goal.actionIds.length||new Set(goal.actionIds).size!==goal.actionIds.length||!Number.isFinite(goal.usValue)||!Number.isFinite(goal.opponentValue)||Math.abs(goal.usValue)>1e9||Math.abs(goal.opponentValue)>1e9)throw new Error('Each goal needs an ID, linear/all type, unique required action IDs, and finite utility values.');
  return {...goal,mask:maskOf(goal.actionIds)};
 });
 if(new Set(goals.map(x=>x.id)).size!==goals.length)throw new Error('Goal IDs must be unique.');
 const rounds=g.maxOffers??3,cap=g.maxActionsPerSide??2;
 if(!Number.isInteger(rounds)||rounds<1||rounds>4||!Number.isInteger(cap)||cap<1||cap>2)throw new Error('Use 1–4 offers and 1–2 new actions per side for local planning.');
 const count=m=>{let n=0;for(;m;m&=m-1)n++;return n;};
 const total=1<<actions.length,usMask=maskOf(actions.filter(a=>a.owner==='us').map(a=>a.id)),oppMask=(total-1)^usMask,forbidden=maskOf(g.forbiddenActions||[]),start=maskOf(commitments);
 const us=Array(total).fill(0),opp=Array(total).fill(0),sat=Array.from({length:total},()=>[]);
 for(let c=0;c<total;c++)for(const goal of goals){const satisfaction=goal.type==='all'?((c&goal.mask)===goal.mask?1:0):count(c&goal.mask)/goal.actionIds.length;sat[c].push(satisfaction);us[c]+=satisfaction*goal.usValue;opp[c]+=satisfaction*goal.opponentValue;}
 const models=[{id:'baseline',values:goals.map(x=>x.opponentValue)}];
 for(const reading of (g.opponentReadings||[])){
  if(models.length>=17)throw new Error('Local planning supports up to 16 opponent readings.');
  if(typeof reading.id!=='string'||!reading.values||goals.some(goal=>(!Number.isFinite(reading.values[goal.id])||Math.abs(reading.values[goal.id])>1e9)))throw new Error('Opponent readings must supply a finite value for every goal ID.');
  models.push({id:reading.id,values:goals.map(x=>reading.values[x.id])});
 }
 const legal=[];
 for(let add=1;add<total;add++)if(!(add&forbidden)&&count(add&usMask)<=cap&&count(add&oppMask)<=cap)legal.push(add);
 const neighbors=new Map();
 const additions=c=>{if(!neighbors.has(c))neighbors.set(c,legal.filter(add=>!(c&add)));return neighbors.get(c);};
 const paths=[],seen=new Set();
 for(const model of models){
  const values=sat.map(s=>s.reduce((v,x,i)=>v+x*model.values[i],0)),memo=new Map();
  function search(c,left){
   const key=c*5+left;if(memo.has(key))return memo.get(key);
   let best={value:us[c],path:[]};
   if(left)for(const add of additions(c)){
    const next=c|add;if(values[next]+1e-9<values[c])continue;
    const rest=search(next,left-1);
    if(rest.value>best.value+1e-9)best={value:rest.value,path:[add,...rest.path]};
   }
   memo.set(key,best);return best;
  }
  const path=search(start,rounds).path,key=path.join(',');if(path.length&&!seen.has(key)){seen.add(key);paths.push({path,origin:model.id});}
 }
 const low=goals.reduce((n,x)=>n+Math.min(0,x.usValue),0),high=goals.reduce((n,x)=>n+Math.max(0,x.usValue),0),norm=value=>high===low?0:Math.max(0,Math.min(1,(value-low)/(high-low)));
 const actionIds=mask=>actions.filter((a,i)=>mask&(1<<i)).map(a=>a.id);
 const describe=mask=>['us','opponent'].map(owner=>{const labels=actions.filter((a,i)=>a.owner===owner&&(mask&(1<<i))).map(a=>a.label);return labels.length?`${p.parties[owner]}: ${labels.join('; ')}`:null;}).filter(Boolean).join(' ↔ ');
 const candidates=paths.map(({path,origin},i)=>{
  const scores=models.map(model=>{let c=start;for(const add of path){const next=c|add,delta=sat[next].reduce((v,x,i)=>v+(x-sat[c][i])*model.values[i],0);if(delta< -1e-9)break;c=next;}return us[c];});
  return {id:`local-plan-${i+1}`,title:`Commitment option ${i+1}`,opening:describe(path[0]),fallback:p.walkAway||'Pause and review the outside option if the offer is rejected.',actionIds:actionIds(path[0]),steps:path.map(actionIds),meanScore:scores.reduce((n,x)=>n+norm(x),0)/scores.length,worstScore:Math.min(...scores.map(norm)),rawMean:scores.reduce((a,b)=>a+b,0)/scores.length,rawWorst:Math.min(...scores),baselineValue:us[start],origin,method:'local-exact',freshRescored:false,redLines:[],assumptions:['Commitments are binding and additive.','Opponent responses follow the supplied utility model; tactical behavior is not modeled.','Utilities and goals supplied by the game builder require team review.','Textual red lines must be encoded as forbidden actions or constraints in the supplied game; this planner does not infer them.'],ethicsFlags:['No automated ethics review has been run. Review this option before use.'],branches:path.slice(1).map((mask,j)=>`After acceptance, offer ${j+2}: ${describe(mask)}`).concat('If rejected: pause this sequence and review the model; no commitment is added.')};
 }).filter(x=>x.rawMean>=us[start]-1e-9).sort((a,b)=>b.worstScore-a.worstScore||b.meanScore-a.meanScore).slice(0,5);
 return {strategies:candidates,report:{method:'Exact bounded search over our offers, with modeled accept/reject responses',actionCount:actions.length,offerHorizon:rounds,models:models.length,baselineValue:us[start],generatedAt:new Date().toISOString(),note:'This is a bounded offer-sequence model, not a full alternating-proposer equilibrium. Scores are estimates on supplied games, not certified stability or observed outcomes.'}};
}
if(typeof module!=='undefined')module.exports={planPackage};else if(typeof document==='undefined')root.onmessage=e=>{try{root.postMessage({ok:true,result:planPackage(e.data.package,e.data.commitments)});}catch(err){root.postMessage({ok:false,error:err.message});}};else root.LocalPlanner={planPackage};
})(typeof self!=='undefined'?self:globalThis);
