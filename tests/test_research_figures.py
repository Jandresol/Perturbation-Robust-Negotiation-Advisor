import json
from backend.research_figures import build_figures, measurements, PLOTS


def package(rejected=False):
    return {'title':'Current case','sources':[{'id':'s','title':'Role instructions'}], 'facts':[{'id':'f','text':'Original terms','sourceId':'s'},{'id':'g','text':'Second original','sourceId':'s'}], 'variants':[
        {'id':'v','factId':'f','text':'Reworded terms','method':'peer-semantic-v1','frame':'Semantic paraphrase · light','validation':json.dumps({'accepted':not rejected,'reject_reason':'nli_fwd' if rejected else None,'cos':.94,'d_emb':.06,'nli_fwd':.3 if rejected else .96,'nli_bwd':.97,'nli_threshold':.5})},
        {'id':'w','factId':'g','text':'Second rewording','validation':{'accepted':True,'operator':'paraphrase_doc','level':'heavy','cos':.98,'d_emb':.02,'nli_fwd':.99,'nli_bwd':.98,'noise_d_emb':.021}}]}


def test_figures_have_all_six_png_pdf_and_csv_artifacts_and_reuse_cache(tmp_path,monkeypatch):
    p=package();manifest=build_figures(p,tmp_path);root=tmp_path/manifest['key']
    for name in PLOTS:
        assert (root/f'{name}.png').read_bytes().startswith(b'\x89PNG')
        assert (root/f'{name}.pdf').read_bytes().startswith(b'%PDF')
    csv=(root/'measurements.csv').read_text();assert 'Original terms' in csv;assert 'Second rewording' in csv
    import backend.research_figures as module
    monkeypatch.setattr(module,'_render',lambda *_: (_ for _ in ()).throw(AssertionError('cached figures must not render again')))
    assert build_figures(p,tmp_path)==manifest


def test_different_case_results_have_different_artifact_keys(tmp_path):
    a=build_figures(package(),tmp_path);b=build_figures(package(True),tmp_path)
    assert a['key']!=b['key'];assert a['accepted']==2;assert b['accepted']==1


def test_missing_metrics_are_not_zero_and_legacy_operator_strength_are_recovered():
    p=package();p['variants'][0]['validation']=json.dumps({'accepted':True,'d_emb':None,'nli_fwd':None})
    rows=measurements(p);assert rows[0]['operator']=='paraphrase_fact';assert rows[0]['level']=='light';assert rows[0]['d_emb'] is None;assert rows[0]['nli_fwd'] is None
    p['variants']=[{'validation':'Local comparison','outcome':'stable'}];assert measurements(p)==[]
