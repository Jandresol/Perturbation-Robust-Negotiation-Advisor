/* Timed preparation orchestration, following Detailed_Plan §18.2. */
(function(root){
  const STOP_GENERATION_MS=5*60*1000, BRIEF_MS=6*60*1000;
  function context(p){
    const name=x=>typeof x==='string'&&!/not inferred|^our side$|^opponent$|^unknown$/i.test(x)?x:null;
    return {our_side:name(p.parties?.us),opponent:name(p.parties?.opponent),objective:p.objective||null,outside_option:p.walkAway||null,red_line_decisions:(p.caseEdits?.redLines||[]).map(r=>({text:r.text,status:r.status,claim_ids:r.factIds})),confirmed_red_lines:(p.caseEdits?.redLines||[]).filter(r=>r.status==='confirmed').map(r=>({text:r.text,claim_ids:r.factIds})),corrected_claims:p.facts.filter(f=>f.corrected).map(f=>({id:f.id,text:f.text}))};
  }
  function isBriefStale(p){return !!p.sourceAnalysis?.briefContext&&p.sourceAnalysis.briefContext!==JSON.stringify(context(p));}
  function issues(p){
    const found=[],add=x=>{if(!found.some(v=>v.detail===x.detail))found.push(x);};
    if(!p.sources.some(s=>s.category==='role_card'||(!s.category&&s.visibility==='private'))&&!p.sourceAnalysis?.caseAnalysis?.our_side&&(!p.parties?.us||/^(our side.*|unknown)$/i.test(p.parties.us)))add({id:'role',title:'Confirm our side',detail:'Identify our role card or confirm whom we represent in Case & constraints before relying on role-specific advice.'});
    for(const issue of p.sourceAnalysis?.caseAnalysis?.issues||[])add({id:`source-${found.length}`,title:'Decision to clarify',detail:issue.text,factIds:issue.claim_ids});
    for(const s of p.sources){
      if(s.emptyPages?.length)add({id:`ocr-${s.id}`,title:'Source pages need OCR',detail:`${s.title}: pages ${s.emptyPages.join(', ')}.`,sourceId:s.id,page:s.emptyPages[0]});
      const limitations=(s.analysis?.limitations||[]).filter(t=>/excluded|unverified|unreadable|truncat|ocr|conflict/i.test(t));
      if(limitations.length)add({id:`coverage-${s.id}`,title:'Evidence coverage needs review',detail:`${s.title}: ${limitations.join(' ')}`,sourceId:s.id});
    }
    for(const text of p.game?.assumptions||[])if(typeof text==='string')add({id:`assumption-${found.length}`,title:'Game assumption',detail:text});
    for(const strategy of p.strategies)for(const text of strategy.ethicsFlags||[])add({id:`ethics-${found.length}`,title:'Advisory concern',detail:text});
    return found;
  }
  function draftBrief(p){
    const team=p.preparation?.brief||{},caseAnalysis=p.sourceAnalysis?.caseAnalysis||{},advice=caseAnalysis.brief||{},chosen=p.strategies.find(x=>x.id===p.preparation?.chosenStrategyId)||p.strategies[0];
    const plan=chosen?.referenceOnly?null:chosen;
    const text=x=>typeof x==='string'?x:x?.text||'';
    const preferred=new Set(advice.critical_claim_ids||[]),sources=new Map(p.sources.map(s=>[s.id,s]));
    const weights={constraint:10,commitment:9,goal:8,condition:7,timeline:6,resource:4,context:0};
    const score=f=>(preferred.has(f.id)?100:0)+(sources.get(f.sourceId)?.category==='role_card'?12:sources.get(f.sourceId)?.visibility==='private'?6:0)+(weights[f.category]||0)+(/authoriz|authority|consent|deadline|release|refus|permission|approval/i.test(f.text)?3:0);
    const facts=[...p.facts].sort((a,b)=>score(b)-score(a)).slice(0,3).map(f=>({...f,kind:'extracted fact'}));
    const indexed=p.preparation?.candidates||[],evidence=facts.length?facts:indexed.filter(c=>c.status!=='rejected').sort((a,b)=>Number(['constraint','goal','condition','resource'].includes(b.category))-Number(['constraint','goal','condition','resource'].includes(a.category))).slice(0,3).map(c=>({...c,kind:'source passage'}));
    const redLines=p.caseEdits?.redLines?p.caseEdits.redLines.filter(r=>r.status!=='dismissed').map(r=>`${r.text}${r.status==='inferred'?' (inferred)':''}`):team.redLines?.length?team.redLines:advice.our_constraints?advice.our_constraints.filter(x=>x.status!=='unknown').map(x=>text(x)+' (inferred; team confirmation needed)'):plan?.redLines?.length?plan.redLines:(caseAnalysis.red_lines||[]).map(x=>x.text+' (inferred; ownership needs review)');
    return {briefStale:isBriefStale(p),title:p.title,objective:p.objective||caseAnalysis.objective||'Confirm our side and objective in Case & constraints.',outsideOption:p.walkAway||caseAnalysis.outside_option||'Unknown: establish what we can do if no agreement is reached.',opening:team.opening||plan?.opening||text(advice.opening)||null,fallback:team.fallback||plan?.fallback||text(advice.fallback)||null,redLines,alternatives:plan?p.strategies.filter(x=>x.id!==plan.id&&!x.referenceOnly).slice(0,2).map(x=>x.opening):(advice.alternatives||[]).map(text),opponentDemands:advice.opponent_demands||[],authority:advice.decision_authority||null,tradeoffs:advice.tradeoffs||[],assumptions:(team.assumptions?.length?team.assumptions:plan?.assumptions?.length?plan.assumptions:(advice.critical_assumptions||[]).map(text)).slice(0,3),branches:team.branches?.length?team.branches:plan?.branches?.length?plan.branches:(advice.response_branches||[]).map(text),evidence,issues:issues(p).slice(0,5),advice,status:plan?'plan-available':advice.opening?'advisory-brief':'source-draft'};
  }
  function canGenerate(run,now=Date.now()){return !!run&&run.status==='running'&&now-run.startedAt<STOP_GENERATION_MS;}
  const api={STOP_GENERATION_MS,BRIEF_MS,context,isBriefStale,issues,draftBrief,canGenerate};
  if(typeof module!=='undefined')module.exports=api;else root.PrepWorkflow=api;
})(typeof window!=='undefined'?window:globalThis);
