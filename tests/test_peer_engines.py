import copy
import json
import re
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.engines import PeerEngines, build_peer_game, game_signature
from backend.inference import AnalysisService

ROOT = Path(__file__).resolve().parents[1]


class PeerEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.package = json.loads((ROOT/'example-package.json').read_text())
        self.service = PeerEngines(AnalysisService(Path(self.tmp.name)/'test.sqlite', transport=lambda prompt: ({'rewordings':['Team A is able to provide a workshop.']}, (10,10))))

    def tearDown(self):
        self.tmp.cleanup()

    def wait(self, job_id):
        for _ in range(200):
            job=self.service.get(job_id)
            if job['status'] not in ('queued','running'):return job
            time.sleep(.01)
        self.fail('Engine job timed out')

    def test_game_preserves_canonical_facts_and_marks_heuristic_utilities(self):
        original=copy.deepcopy(self.package)
        built=build_peer_game(self.package)
        self.assertEqual(built['facts'], original['facts'])
        self.assertEqual(self.package, original)
        self.assertTrue(built['game']['illustrativeUtilities'])
        self.assertTrue(built['strategies'])
        self.assertTrue(all(s['method']=='peer-solver' for s in built['strategies']))
        self.assertEqual(game_signature(built), game_signature(build_peer_game(self.package)))

    def test_rejects_changed_canonical_provenance(self):
        self.package['facts'][0]['quote']='A quote that does not occur in the source.'
        with self.assertRaisesRegex(ValueError, 'canonical facts'):
            build_peer_game(self.package)

    def test_async_game_deduplicates_and_supports_cancel(self):
        request={'engine':'game','package':self.package}
        first=self.service.start(request)
        job=self.wait(first['jobId'])
        self.assertEqual(job['status'],'complete')
        self.assertEqual(self.service.start(request)['jobId'],first['jobId'])
        self.assertEqual(job['result']['packageId'],self.package['id'])
        self.assertEqual(self.service.cancel(first['jobId'])['status'],'cancelling')

    def test_frozen_fact_requirement(self):
        with self.assertRaisesRegex(ValueError,'frozen'):
            self.service.start({'engine':'perturbation','package':self.package})

    def test_failed_paid_output_is_reused_without_another_gateway_call(self):
        import io
        from negotiator.reword import engine, embed, filter as filters
        from negotiator import llm
        database=Path(self.tmp.name)/'gateway.sqlite'
        raw={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'rewordings':'not-an-array'})}}], 'usage':{'prompt_tokens':20,'completion_tokens':5}}
        def generate(units,cfg):
            llm.complete_json('fixed prompt', {'type':'object'}, seed=0)
            return [],[]
        with patch.dict('os.environ',{'HUIT_API_KEY':'test-only-not-real','HUIT_PROVIDER':'openai','HUIT_MODEL':'gpt-4.1-mini'}),patch('urllib.request.urlopen',side_effect=lambda *a,**kw:io.BytesIO(json.dumps(raw).encode())) as network,patch.object(engine,'run',side_effect=generate),patch.object(embed,'cosine',return_value=1),patch.object(filters,'entailment',return_value=1):
            for _ in range(2):
                self.service=PeerEngines(AnalysisService(database))
                job_id=self.service.start({'engine':'perturbation','factSetFrozen':True,'package':self.package})['jobId']
                job=self.wait(job_id)
                self.assertEqual(job['status'],'failed')
                self.assertIn('paid response is retained',job['error'])
            self.assertEqual(network.call_count,1)

    def test_semantic_engine_is_adapted_then_rebuilds_and_scores_each_reading(self):
        from negotiator.reword import engine, embed, filter as filters
        from negotiator import llm
        calls=[]
        def fake_run(units,cfg):
            unit=units[0]
            data,meta=llm.complete_json('Reword '+unit['text'],{'type':'object'},seed=0)
            calls.append((cfg,meta))
            text=unit['text'].replace('can provide','is able to provide')
            if text==unit['text']:text=unit['text']+' '
            return [{'source_id':unit['id'],'text':text,'accepted':True,'operator':'paraphrase_fact','level':'light','cos':.99,'nli_fwd':.99,'nli_bwd':.99,'hard_facts_ok':True,**meta}],[]
        original=copy.deepcopy(self.package)
        with patch.object(engine,'run',side_effect=fake_run),patch.object(embed,'cosine',return_value=1),patch.object(filters,'entailment',return_value=1):
            started=self.service.start({'engine':'perturbation','factSetFrozen':True,'package':self.package})
            job=self.wait(started['jobId'])
        self.assertEqual(job['status'],'complete',job.get('error'))
        result=job['result']
        self.assertTrue(result['variants'])
        self.assertTrue(all(v['comparisonCompleted'] for v in result['variants']))
        self.assertFalse(any(result['release'].values()))
        self.assertLessEqual(len(calls),16)
        self.assertTrue(all(c[0]['noise']['enabled'] is False for c in calls))
        self.assertEqual(self.package,original)
        self.assertGreater(result['generation']['shortfall'],0)

    def test_document_rewording_reextracts_then_rebuilds_and_compares(self):
        from negotiator.reword import engine, embed, filter as filters
        same='Team A is able to provide a workshop. Team B is able to provide a review session. Either team may continue with a separate project. Both teams must agree on scope and dates.'
        moved='Team A could offer a workshop. Team B is able to provide a review session. Either team may continue with a separate project. Both teams must agree on scope and dates.'
        rejected='Team A refuses to provide a workshop.'
        def fake_run(units,cfg):
            unit=units[0]
            self.assertEqual(unit['kind'],'doc')
            rec={'source_id':unit['id'],'operator':'paraphrase_doc','level':'light','cos':.99,'nli_fwd':.99,'nli_bwd':.99,'hard_facts_ok':True,'reject_reason':None,'model':'m','prompt_hash':'h'}
            return [{**rec,'text':same,'accepted':True},{**rec,'text':moved,'accepted':True},
                    {**rec,'text':rejected,'accepted':False,'reject_reason':'nli'}],[]
        extracted=[];prefetched=[]
        def transport(prompt):
            task=json.loads(prompt)
            if task['task']=='rewording':
                prefetched.append(task['prompt'])  # engine.run is faked; the job still warms the gateway cache
                return {'rewordings':[same]},(10,10)
            self.assertEqual(task['task'],'document')
            text=task['input']['text'];extracted.append(text)
            quotes=re.split(r'(?<=\.) ',text)
            # The second rewording leads the extractor to read Team A's offer as context, so it is no longer an action.
            claims=[{'text':'Team A can provide a workshop.','quote':quotes[0],'category':'context' if text==moved else 'commitment'},
                    {'text':'Team B can provide a review session.','quote':quotes[1],'category':'commitment'},
                    {'text':'Scope and dates need joint agreement.','quote':quotes[3],'category':'goal'}]
            return {'document_type':'other','summary':'s','tags':[],'entities':[],'represented_side':None,'limitations':[],'arguments':[],
                    'claims':[{**c,'attribution':'source','modality':'asserted','conditions':[]} for c in claims]},(10,10)
        vocab={}
        def fake_embed(texts,name):
            import numpy as np
            rows=np.zeros((len(texts),16))
            for i,t in enumerate(texts):rows[i,vocab.setdefault(t,len(vocab))]=1
            return rows
        self.service=PeerEngines(AnalysisService(Path(self.tmp.name)/'doc.sqlite',transport=transport))
        original=copy.deepcopy(self.package)
        with patch.object(engine,'run',side_effect=fake_run),patch.object(embed,'cosine',return_value=1),patch.object(filters,'entailment',return_value=1),patch.object(embed,'embed',side_effect=fake_embed):
            job=self.wait(self.service.start({'engine':'perturbation-doc','factSetFrozen':True,'package':self.package})['jobId'])
        self.assertEqual(job['status'],'complete',job.get('error'))
        variants={v['text']:v for v in job['result']['variants']}
        self.assertEqual(variants[same]['outcome'],'stable')
        self.assertEqual(variants[same]['facts'],{'baseline':3,'reextracted':3,'matched':3})
        self.assertEqual(variants[moved]['outcome'],'changed')
        self.assertEqual(variants[rejected]['outcome'],'rejected')
        # The original text (the baseline) and both accepted rewordings are extracted; the rejected one never is.
        self.assertEqual(sorted(extracted),sorted([self.package['sources'][0]['text'],same,moved]))
        self.assertEqual(len(prefetched),6)  # 2 operators x 3 levels, in one concurrent wave
        self.assertEqual(job['result']['generation']['extractions'],3)
        self.assertEqual(self.package,original)

    def test_document_rewording_requires_frozen_facts(self):
        with self.assertRaisesRegex(ValueError,'frozen'):
            self.service.start({'engine':'perturbation-doc','package':self.package})

    def test_align_facts_is_one_to_one_and_leaves_dissimilar_facts_unmatched(self):
        import numpy as np
        from backend.engines import align_facts
        vectors={'a':[1,0,0],'a2':[1,0,0],'b':[0,1,0],'c':[0,0,1]}
        new=[{'id':'n1','text':'a'},{'id':'n2','text':'a2'},{'id':'n3','text':'c'}]
        old=[{'id':'o1','text':'a'},{'id':'o2','text':'b'}]
        with patch('negotiator.reword.embed.embed',side_effect=lambda texts,name:np.array([vectors[t] for t in texts],float)):
            out=align_facts(new,old,'enc',.85)
        self.assertEqual(len(out),1)
        self.assertEqual(set(out.values()),{'o1'})


if __name__=='__main__':unittest.main()
