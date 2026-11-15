"""Fable review pilot (2026-10-27): does rewording the role card change the model-written brief
more than re-running the same text does?  Arms: B2 = same text x3 (separate cache scopes),
RW = up to 4 accepted document-level rewordings of the role card, one run each.
Recommendation compared = caseAnalysis.brief (opening, fallback, alternatives, red lines,
constraints, issue titles, trade-offs).  Separate sqlite ledger; nothing touches .data/.
"""
import copy, json, os, random, sys, time, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from backend.inference import AnalysisService, InferenceError, load_env

load_env(ROOT / '.env')
MODEL = 'us.anthropic.claude-fable-5-1'
os.environ['HUIT_PROVIDER'] = 'bedrock'
os.environ['HUIT_MODEL'] = MODEL
DB = OUT / 'pilot.sqlite'
SHARED_SCOPE = 'fable-review-shared'
MAX_CALLS = 40
SHARED_TITLES = ['Copy of Refugee Processing and Transport Protocols.docx',
                 'Copy of Official Message from Border Authority to the Mayor of Qiso.docx',
                 'Message from Central Border Authority.docx',
                 'Copy of National News 1.docx',
                 'Copy of Refugee Facility Requirements.docx']

def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)

def quota():
    key = os.environ.get('ANTHROPIC_API_KEY') or os.environ.get('HUIT_API_KEY')
    req = urllib.request.Request('https://apis.huit.harvard.edu/ais-bedrock-llm/apigee/quota',
                                 headers={'x-api-key': key, 'User-Agent': 'review/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return float(json.loads(r.read().decode())['remaining_limit'])

REWORD_USAGE = []
def patch_reword_llm():
    """Record token usage of negotiator.llm calls (its cache stores no usage)."""
    from negotiator import llm
    def _complete(prompt, schema, model, effort, max_tokens, base_url):
        response = llm._get_client(base_url).messages.create(
            model=model, max_tokens=max_tokens,
            output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': schema}},
            messages=[{'role': 'user', 'content': prompt}])
        REWORD_USAGE.append({'model': response.model, 'input_tokens': response.usage.input_tokens,
                             'output_tokens': response.usage.output_tokens, 'stop': response.stop_reason})
        if response.stop_reason == 'refusal':
            raise RuntimeError(f'model refused: {response.stop_details}')
        if response.stop_reason == 'max_tokens':
            raise RuntimeError('hit max_tokens')
        text = next(b.text for b in response.content if b.type == 'text')
        return json.loads(text), response.model
    llm._complete = _complete

class Scoped(AnalysisService):
    """Sequential extraction so the cache scope can differ per source: shared docs are cached
    once; the role card and the case synthesis get the replicate's scope."""
    def __init__(self, rc_scope, case_scope):
        super().__init__(DB)
        self.rc_scope, self.case_scope = rc_scope, case_scope
    def documents(self, sources, emit, deadline):
        out = []
        for s in sources:
            os.environ['CACHE_SCOPE'] = self.rc_scope if s.get('category') == 'role_card' else SHARED_SCOPE
            d = self.document(s)
            emit({'type': 'source', 'sourceId': s['id'], 'status': 'complete', 'cacheHit': d['cacheHit'], 'claims': len(d['analysis']['claims'])})
            out.append(d)
        os.environ['CACHE_SCOPE'] = self.case_scope
        return out

def calls_so_far():
    import sqlite3
    n = sqlite3.connect(DB).execute('select count(*) from calls').fetchone()[0] if DB.exists() else 0
    return n + len(REWORD_USAGE)

def guard(phase):
    n = calls_so_far()
    log(f'[{phase}] paid calls so far: {n}')
    if n >= MAX_CALLS:
        log('call cap reached; stopping'); sys.exit(2)

def run_case(tag, pkg, rc_scope, case_scope):
    guard(tag)
    svc = Scoped(rc_scope, case_scope)
    t0 = time.time()
    try:
        res = svc.parse(pkg, on_progress=lambda e: log(tag, json.dumps(e)[:160]))
        res['elapsed_s'] = round(time.time() - t0, 1)
        (OUT / f'{tag}.json').write_text(json.dumps(res, indent=1, ensure_ascii=False))
        log(tag, 'OK', res['elapsed_s'], 's; case cache hit:', res['caseCacheHit'])
        return res
    except InferenceError as e:
        log(tag, 'FAILED:', str(e)[:300])
        (OUT / f'{tag}.error.txt').write_text(str(e))
        if '429' in str(e):
            log('budget cap hit (429); stopping'); sys.exit(3)
        return None

def main():
    w = json.load(open(ROOT / 'data' / 'negotiation-workspace.json'))
    full = w['package']
    keep = lambda s: {k: s[k] for k in ('id', 'title', 'category', 'visibility', 'text', 'format', 'pages', 'sections') if k in s}
    rc = next(s for s in full['sources'] if s.get('category') == 'role_card')
    shared = [next(s for s in full['sources'] if s['title'] == t) for t in SHARED_TITLES]
    pkg = {'schemaVersion': 1, 'id': 'fable-review-qiso-subset', 'title': full['title'],
           'parties': full['parties'], 'requireDetailedBrief': True,
           'sources': [keep(rc)] + [keep(s) for s in shared]}
    (OUT / 'package_subset_meta.json').write_text(json.dumps(
        {'sources': [(s['id'], s['title'], s['category'], len(s['text'])) for s in pkg['sources']]}, indent=1))
    q0 = quota(); log('quota remaining before: $%.3f' % q0)
    patch_reword_llm()

    # Phase 0: shared docs once, concurrently.
    guard('shared')
    os.environ['CACHE_SCOPE'] = SHARED_SCOPE
    base = AnalysisService(DB)
    base.documents([keep(s) for s in shared], lambda e: log('shared', json.dumps(e)[:160]), time.monotonic() + 900)

    # Phase 1: B2 same-text x3.
    b2 = {}
    for r in (1, 2, 3):
        b2[f'b2_r{r}'] = run_case(f'b2_r{r}', copy.deepcopy(pkg), f'fable-review-rc-r{r}', f'fable-review-case-r{r}')

    # Phase 2: reword the role card (document level), filter locally, pick up to 4 accepted.
    guard('reword')
    cfg = yaml.safe_load((ROOT / 'configs' / 'default.yaml').read_text())
    cfg['llm']['model'] = MODEL
    cfg['reword'].update(k=2, operators=['paraphrase_doc'], levels=['light', 'moderate', 'heavy'], reorder_k=0)
    cfg['noise']['enabled'] = False
    (OUT / 'fable-review.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False))
    from negotiator.reword import engine
    records, _ = engine.run([{'id': 'rolecard', 'text': rc['text'], 'kind': 'doc'}], cfg)
    (OUT / 'rewordings.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    acc = [r for r in records if r['accepted']]
    log(f'rewordings: {len(records)} candidates, {len(acc)} accepted;',
        {(r['level']): (round(r['d_emb'], 4), r['accepted'], r['reject_reason']) for r in records})
    chosen, by_level = [], {}
    for r in acc: by_level.setdefault(r['level'], []).append(r)
    while len(chosen) < 4 and any(by_level.values()):
        for lvl in ('light', 'moderate', 'heavy'):
            if by_level.get(lvl) and len(chosen) < 4: chosen.append(by_level[lvl].pop(0))
    # Phase 3: one run per accepted rewording.
    rw = {}
    for i, rec in enumerate(chosen, 1):
        p = copy.deepcopy(pkg)
        p['sources'][0] = {**p['sources'][0], 'text': rec['text'], 'pages': [], 'sections': []}
        res = run_case(f'rw_{i}', p, 'fable-review-rw', 'fable-review-rw')
        rw[f'rw_{i}'] = {'result': res, 'rewording': rec}

    q1 = quota(); log('quota remaining after: $%.3f  spent: $%.3f' % (q1, q0 - q1))
    import sqlite3
    db = sqlite3.connect(DB)
    ledger = [dict(zip(('kind', 'model', 'n', 'input_tokens', 'output_tokens'), r)) for r in
              db.execute('select kind, model, count(*), sum(input_tokens), sum(output_tokens) from calls group by kind, model')]
    json.dump({'model': MODEL, 'quota_before': q0, 'quota_after': q1, 'spent_usd': round(q0 - q1, 4),
               'ledger': ledger, 'reword_usage': REWORD_USAGE, 'chosen_rewordings': [r['id'] for r in chosen],
               'b2_ok': {k: v is not None for k, v in b2.items()}, 'rw_ok': {k: v['result'] is not None for k, v in rw.items()}},
              open(OUT / 'pilot_ledger.json', 'w'), indent=1)
    log('done')

if __name__ == '__main__':
    main()
