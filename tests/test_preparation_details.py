import json
from pathlib import Path
from backend.inference import AnalysisService, InferenceError
import test_inference as fixtures
import pytest


def test_original_role_passages_support_detail_without_becoming_canonical_facts(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    try:
        def transport(prompt):
            data=json.loads(prompt);value,counts=helper.transport(prompt)
            if data['task']=='case':
                passage=data['input'][0]['original_priority_text'][0]
                entry={'text':'A decision recorded in the original role instructions.','claim_ids':[],'source_passage_ids':[passage['id']],'status':'supported'}
                value['negotiation_issues']=[{'title':'Equipment delivery conditions','decision':[entry],'counterpart_position':[entry]}]
                value['preparation_context']={'immediate_decision':[entry]}
            return value,counts
        service=AnalysisService(tmp_path/'test.sqlite',transport)
        result=service.parse(helper.package())
        assert len(result['facts'])==1
        assert result['sourcePassages'][0]['text']==helper.source['text']
        assert result['sourcePassages'][0]['sourceId']==helper.source['id']
        assert result['caseAnalysis']['negotiation_issues'][0]['counterpart_position'][0]['status']=='supported'
        assert service.parse(helper.package())['caseCacheHit']
    finally: helper.tearDown()


def test_unknown_original_passage_is_quarantined_without_a_paid_retry(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    try:
        def transport(prompt):
            value,counts=helper.transport(prompt)
            if json.loads(prompt)['task']=='case':
                value['negotiation_issues']=[{'title':'Decision','decision':[{'text':'Unsupported','status':'supported','claim_ids':[],'source_passage_ids':['invented']}]}]
            return value,counts
        result=AnalysisService(tmp_path/'test.sqlite',transport).parse(helper.package())
        item=result['caseAnalysis']['negotiation_issues'][0]['decision'][0]
        assert item['status']=='unknown'
        assert item['source_passage_ids']==[]
        assert item['claim_ids']==[]
    finally: helper.tearDown()


def test_uncited_question_is_unknown_not_a_failed_paid_analysis(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    try:
        def transport(prompt):
            value,counts=helper.transport(prompt)
            if json.loads(prompt)['task']=='case':
                value['negotiation_issues']=[{'title':'Decision','questions':[{'text':'Who can approve delivery?','status':'inferred','claim_ids':[]}]}]
            return value,counts
        result=AnalysisService(tmp_path/'test.sqlite',transport).parse(helper.package())
        assert result['caseAnalysis']['negotiation_issues'][0]['questions'][0]['status']=='unknown'
    finally: helper.tearDown()


def test_refresh_contract_requires_issue_synthesis_and_retains_cached_documents(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    try:
        service=AnalysisService(tmp_path/'test.sqlite',helper.transport)
        service.parse(helper.package())  # Valid older schema remains readable.
        with pytest.raises(InferenceError,match='did not include the negotiation issue synthesis'):
            service.parse({**helper.package(),'requireDetailedBrief':True})
        assert helper.calls==['document','case','case']
    finally: helper.tearDown()


def test_saved_text_wrapper_shape_is_normalized_without_regeneration(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    try:
        def transport(prompt):
            value,counts=helper.transport(prompt)
            if json.loads(prompt)['task']=='case':
                claim_id=json.loads(prompt)['input'][0]['analysis']['claims'][0]['id']
                for key in ['title','summary','our_side','opponent','objective','outside_option']:
                    value[key]={'text':value[key],'status':'supported','claim_ids':[claim_id]}
                value['negotiation_issues']=[{'title':'Equipment delivery','decision':[{'text':'Agree delivery conditions.','status':'supported','claim_ids':[claim_id]}]}]
            return value,counts
        service=AnalysisService(tmp_path/'test.sqlite',transport)
        request={**helper.package(),'requireDetailedBrief':True}
        first=service.parse(request);second=service.parse(request)
        assert first['caseAnalysis']['title']=='Equipment discussion'
        assert second['caseCacheHit']
        assert helper.calls==['document','case']
    finally: helper.tearDown()


def test_numeric_condition_in_same_role_paragraph_survives_synthesis_and_cache(tmp_path):
    helper=fixtures.InferenceTests();helper.setUp()
    helper.source['text']='You represent Team A. We need 250 units.'
    helper.source['sections']=[{'number':1,'text':helper.source['text']}]
    try:
        def transport(prompt):
            value,counts=helper.transport(prompt)
            if json.loads(prompt)['task']=='document':
                value['claims'].append({'text':'Our side needs 250 units.','quote':'We need 250 units.','attribution':'role instructions','modality':'asserted','conditions':[],'category':'resource'})
            else:
                claim_id=json.loads(prompt)['input'][0]['analysis']['claims'][0]['id']
                value['negotiation_issues']=[{'title':'Equipment delivery','decision':[{'text':'Agree delivery conditions.','status':'supported','claim_ids':[claim_id]}]}]
            return value,counts
        service=AnalysisService(tmp_path/'test.sqlite',transport)
        for _ in range(2):
            result=service.parse({**helper.package(),'requireDetailedBrief':True})
            assert len(result['facts'])==2
            assert [x['text'] for x in result['caseAnalysis']['negotiation_issues'][0]['conditions']]==['Our side needs 250 units.']
    finally: helper.tearDown()
