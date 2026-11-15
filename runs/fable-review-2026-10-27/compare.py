"""Structured diff of the pilot briefs: within same-text (B2) vs reworded (RW) vs across.
Embedding similarity with the project's encoder; one optional judge call (separate from the brief calls)."""
import itertools, json, os, random, statistics as st, sys
from pathlib import Path
OUT = Path(__file__).resolve().parent; ROOT = OUT.parents[1]; sys.path.insert(0, str(ROOT))
import yaml
from negotiator.reword.embed import embed
ENC = yaml.safe_load((ROOT / 'configs/default.yaml').read_text())['filter']['encoder']
MATCH = 0.80

def fields(res):
    ca = res['caseAnalysis']; b = ca.get('brief') or {}
    t = lambda x: ((x or {}).get('text') or '').strip()
    return {'opening': t(b.get('opening')), 'fallback': t(b.get('fallback')),
            'alternatives': [t(x) for x in b.get('alternatives', [])],
            'red_lines': [x['text'] for x in ca.get('red_lines', [])],
            'our_constraints': [t(x) for x in b.get('our_constraints', [])],
            'issues': [i['title'] for i in ca.get('negotiation_issues', [])],
            'tradeoffs': [x['proposal'] for x in b.get('tradeoffs', [])],
            'objective': ca.get('objective') or '', 'outside_option': ca.get('outside_option') or '',
            'our_side': ca.get('our_side'), 'n_facts': len(res['facts']),
            'rc_claims': next((len(d['analysis']['claims']) for d in res['documents'] if d['sourceId'] == res['documents'][0]['sourceId']), None)}

def cos(a, b):
    if not a or not b: return 0.0
    v = embed([a, b], ENC); return float(v[0] @ v[1])

def soft_jaccard(A, B):
    if not A and not B: return 1.0
    if not A or not B: return 0.0
    va, vb = embed(A, ENC), embed(B, ENC); S = va @ vb.T
    ma = sum(S[i].max() >= MATCH for i in range(len(A))); mb = sum(S[:, j].max() >= MATCH for j in range(len(B)))
    return (ma + mb) / (len(A) + len(B))

def pair_metrics(f, g):
    return {'opening': cos(f['opening'], g['opening']), 'fallback': cos(f['fallback'], g['fallback']),
            'objective': cos(f['objective'], g['objective']),
            'alternatives': soft_jaccard(f['alternatives'], g['alternatives']),
            'red_lines': soft_jaccard(f['red_lines'], g['red_lines']),
            'our_constraints': soft_jaccard(f['our_constraints'], g['our_constraints']),
            'issues': soft_jaccard(f['issues'], g['issues']), 'tradeoffs': soft_jaccard(f['tradeoffs'], g['tradeoffs'])}

def main():
    runs = {}
    for p in sorted(OUT.glob('b2_r*.json')) + sorted(OUT.glob('rw_*.json')):
        runs[p.stem] = fields(json.loads(p.read_text()))
    rew = {}
    if (OUT / 'rewordings.jsonl').exists():
        rew = {r['id']: r for r in map(json.loads, (OUT / 'rewordings.jsonl').read_text().splitlines())}
    ledger = json.loads((OUT / 'pilot_ledger.json').read_text()) if (OUT / 'pilot_ledger.json').exists() else {}
    chosen = ledger.get('chosen_rewordings', [])
    groups = {'B2-B2': [], 'RW-B2': [], 'RW-RW': []}
    pairs = {}
    for a, b in itertools.combinations(runs, 2):
        m = pair_metrics(runs[a], runs[b]); pairs[f'{a}|{b}'] = m
        kind = 'B2-B2' if a.startswith('b2') and b.startswith('b2') else 'RW-RW' if a.startswith('rw') and b.startswith('rw') else 'RW-B2'
        groups[kind].append(m)
    summary = {}
    for kind, ms in groups.items():
        if ms: summary[kind] = {k: {'mean': round(st.mean(m[k] for m in ms), 3), 'min': round(min(m[k] for m in ms), 3), 'n': len(ms)} for k in ms[0]}
    out = {'runs': runs, 'pairs': pairs, 'summary': summary,
           'rewordings_used': [{k: rew[i][k] for k in ('id', 'level', 'd_emb', 'cos', 'nli_fwd', 'nli_bwd')} for i in chosen if i in rew]}
    # Judge: one call, separate from the brief calls, items anonymised and shuffled.
    if '--judge' in sys.argv and runs:
        from negotiator import llm
        cfg = yaml.safe_load((OUT / 'fable-review.yaml').read_text())
        items = list(runs.items()); random.Random(7).shuffle(items)
        anon = [{'id': f'P{i+1}', 'opening': f['opening'], 'fallback': f['fallback']} for i, (_, f) in enumerate(items)]
        prompt = ('Below are negotiation briefs for the same case. For each, name the opening strategy archetype in at most 6 words and '
                  'assign a cluster number so that briefs recommending the same strategic move (same concession offered or asked, same '
                  'sequencing) share a cluster; differences in wording alone do not separate clusters. Then do the same for the fallback.\n\n'
                  + json.dumps(anon, ensure_ascii=False, indent=1))
        schema = {'type': 'object', 'properties': {'items': {'type': 'array', 'items': {'type': 'object', 'properties': {
            'id': {'type': 'string'}, 'opening_archetype': {'type': 'string'}, 'opening_cluster': {'type': 'integer'},
            'fallback_archetype': {'type': 'string'}, 'fallback_cluster': {'type': 'integer'}},
            'required': ['id', 'opening_archetype', 'opening_cluster', 'fallback_archetype', 'fallback_cluster'], 'additionalProperties': False}}},
            'required': ['items'], 'additionalProperties': False}
        data, meta = llm.complete_json(prompt, schema, model=cfg['llm']['model'], base_url=cfg['llm']['base_url'], effort='low', max_tokens=6000, seed=0)
        back = {f'P{i+1}': name for i, (name, _) in enumerate(items)}
        out['judge'] = {'model': meta['model'], 'prompt_hash': meta['prompt_hash'],
                        'items': [{**x, 'run': back[x['id']]} for x in data['items']]}
    (OUT / 'pilot_results.json').write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1)); print(json.dumps(out.get('judge', {}).get('items'), indent=1))
    for k, f in runs.items(): print(k, '| opening:', f['opening'][:200]); print('   fallback:', f['fallback'][:160]); print('   issues:', f['issues'])

if __name__ == '__main__': main()
