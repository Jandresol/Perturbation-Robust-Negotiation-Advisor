import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.inference import AnalysisService, InferenceError


class InferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'cache.sqlite'
        self.calls = []
        self.source = {'id': 's1', 'title': 'role.docx', 'category': 'role_card', 'text': 'You represent Team A. Team B needs equipment.', 'sections': [{'number': 1, 'text': 'You represent Team A. Team B needs equipment.'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def transport(self, prompt):
        data = json.loads(prompt)
        self.calls.append(data['task'])
        if data['task'] == 'document':
            return {'document_type': 'role_card', 'summary': 'Instructions for Team A.', 'tags': ['equipment'], 'entities': [{'name': 'Team A', 'role': 'our organization'}, {'name': 'Team B', 'role': 'counterparty'}], 'represented_side': 'Team A', 'claims': [{'text': 'We represent Team A.', 'quote': 'You represent Team A.', 'attribution': 'role instructions', 'modality': 'asserted', 'conditions': [], 'category': 'context'}], 'arguments': [{'position': 'Team A is the represented side.', 'speaker': 'instructions', 'premise_claim_indexes': [0], 'kind': 'attributed_position'}], 'limitations': []}, (200, 100)
        claim_id = data['input'][0]['analysis']['claims'][0]['id']
        return {'title': 'Equipment discussion', 'summary': 'Team A and Team B discuss equipment.', 'our_side': 'Team A', 'opponent': 'Team B', 'objective': None, 'outside_option': None, 'red_lines': [], 'issues': [{'text': 'No objective supplied.', 'claim_ids': [claim_id]}]}, (100, 50)

    def test_situation_requires_valid_citations_and_preserves_attribution(self):
        def contextual(prompt):
            value, usage = self.transport(prompt)
            data = json.loads(prompt)
            if data['task'] == 'case':
                claim_id = data['input'][0]['analysis']['claims'][0]['id']
                entry = {'text': 'The role instructions identify Team A as our side.', 'status': 'supported', 'claim_ids': [claim_id]}
                value['situation'] = {'immediate': entry, 'actors': [entry], 'tension': entry, 'background': entry, 'uncertainty': []}
            return value, usage
        service = AnalysisService(self.path, contextual)
        result = service.parse(self.package())
        self.assertIn('role instructions', result['caseAnalysis']['situation']['immediate']['text'])
        self.assertTrue(service.parse(self.package())['caseCacheHit'])
        def invalid(prompt):
            value, usage = contextual(prompt)
            if json.loads(prompt)['task'] == 'case':
                value['situation']['immediate']['claim_ids'] = ['unknown-claim']
            return value, usage
        with self.assertRaisesRegex(InferenceError, 'invalid evidence'):
            AnalysisService(Path(self.tmp.name) / 'invalid.sqlite', invalid).parse(self.package())

    def package(self, source=None):
        return {'id': 'p1', 'sources': [source or self.source]}

    def test_reupload_and_server_restart_reuse_all_analysis(self):
        service = AnalysisService(self.path, self.transport)
        first = service.parse(self.package())
        renamed = {**self.source, 'id': 'new-binding', 'title': 'renamed.docx'}
        second = AnalysisService(self.path, self.transport).parse(self.package(renamed))
        self.assertEqual(self.calls, ['document', 'case'])
        self.assertEqual(second['cache']['documentHits'], 1)
        self.assertTrue(second['caseCacheHit'])
        self.assertEqual(second['facts'][0]['sourceId'], 'new-binding')
        self.assertEqual(first['facts'][0]['section'], 1)
        self.assertEqual(first['documents'][0]['analysis']['arguments'][0]['premise_fact_ids'], [first['facts'][0]['id']])

    def test_bucket_change_reuses_document_but_refreshes_case(self):
        service = AnalysisService(self.path, self.transport)
        service.parse(self.package())
        second = service.parse(self.package({**self.source, 'category': 'shared'}))
        self.assertEqual(self.calls, ['document', 'case', 'case'])
        self.assertTrue(second['documents'][0]['cacheHit'])
        self.assertFalse(second['caseCacheHit'])

    def test_bad_quotes_are_saved_but_never_published_or_rebilled(self):
        def bad(prompt):
            result, usage = self.transport(prompt)
            result['claims'][0]['quote'] = 'Invented quotation'
            return result, usage
        service = AnalysisService(self.path, bad)
        for _ in range(2):
            with self.assertRaisesRegex(InferenceError, 'quote'):
                service.parse(self.package())
        self.assertEqual(self.calls, ['document'])

    def test_one_invalid_claim_preserves_valid_claims_and_remaps_arguments(self):
        def mixed(prompt):
            result, usage = self.transport(prompt)
            if json.loads(prompt)['task'] == 'document':
                good = result['claims'][0]
                result['claims'] = [{**good, 'quote': 'Not in the document'}, good]
                result['arguments'] = [
                    {'position': 'Invalid premise', 'speaker': 'source', 'kind': 'attributed_position', 'premise_claim_indexes': [0]},
                    {'position': 'Valid premise', 'speaker': 'source', 'kind': 'attributed_position', 'premise_claim_indexes': [1]}]
            return result, usage
        service = AnalysisService(self.path, mixed)
        result = service.parse(self.package())
        analysis = result['documents'][0]['analysis']
        self.assertEqual(len(result['facts']), 1)
        self.assertEqual(len(analysis['arguments']), 1)
        self.assertEqual(analysis['arguments'][0]['premise_fact_ids'], [result['facts'][0]['id']])
        self.assertIn('1 generated claim(s)', analysis['limitations'][-1])
        self.assertTrue(service.parse(self.package())['caseCacheHit'])
        self.assertEqual(self.calls, ['document', 'case'])

    def test_failed_paid_response_is_reused_after_server_restart(self):
        def bad(prompt):
            result, usage = self.transport(prompt)
            result['claims'][0]['quote'] = 'Unsupported quote'
            return result, usage
        for _ in range(2):
            with self.assertRaisesRegex(InferenceError, 'paid response is saved'):
                AnalysisService(self.path, bad).parse(self.package())
        self.assertEqual(self.calls, ['document'])
        with AnalysisService(self.path)._db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM model_responses').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM artifacts').fetchone()[0], 0)
            self.assertEqual(db.execute('SELECT count(*) FROM calls').fetchone()[0], 1)

    def test_malformed_gateway_output_is_saved_and_never_rebilled(self):
        import io
        from unittest.mock import Mock
        response = {'choices': [{'finish_reason': 'stop', 'message': {'content': 'not JSON'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}
        opener = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(response).encode()))
        with patch.dict(os.environ, {'HUIT_API_KEY': 'test-only', 'HUIT_PROVIDER': 'openai'}), patch('urllib.request.urlopen', opener):
            for _ in range(2):
                with self.assertRaisesRegex(InferenceError, 'saved locally'):
                    AnalysisService(self.path)._request('same prompt')
        self.assertEqual(opener.call_count, 1)

    def test_saved_unknown_argument_reference_recovers_without_new_document_call(self):
        from backend.inference import DOCUMENT_SCHEMA
        def bad_argument(prompt):
            result, usage = self.transport(prompt)
            if json.loads(prompt)['task'] == 'document':
                result['arguments'][0]['premise_claim_indexes'] = [999]
            return result, usage
        service = AnalysisService(self.path, bad_argument)
        def old_validator(result):
            raise InferenceError('Argument references an unknown claim.')
        with self.assertRaises(InferenceError):
            service.artifact('document', {'text': self.source['text']}, DOCUMENT_SCHEMA, old_validator)
        result = AnalysisService(self.path, bad_argument).parse(self.package())
        self.assertEqual(self.calls, ['document', 'case'])
        self.assertEqual(len(result['facts']), 1)
        self.assertEqual(result['documents'][0]['analysis']['arguments'], [])
        self.assertIn('argument(s)', result['documents'][0]['analysis']['limitations'][-1])
        self.assertTrue(result['documents'][0]['cacheHit'])

    def test_structured_brief_uses_cached_documents_and_separates_demands(self):
        def brief_transport(prompt):
            result, usage = self.transport(prompt)
            data = json.loads(prompt)
            if data['task'] == 'case':
                claim = data['input'][0]['analysis']['claims'][0]['id']
                supported = lambda text: {'text':text,'claim_ids':[claim],'status':'inferred'}
                unknown = {'text':'Confirm authority with the team.','claim_ids':[],'status':'unknown'}
                result['brief'] = {'opening':supported('Ask which conditions allow agreement.'),'fallback':unknown,'decision_authority':unknown,'alternatives':[supported('Clarify timing before proposing terms.')],'response_branches':[supported('If authority is unclear, ask who can authorize terms.')],'critical_assumptions':[unknown],'critical_claim_ids':[claim],'our_constraints':[],'opponent_demands':[supported('Counterparty requests equipment.')],'tradeoffs':[{'proposal':'Explore a phased arrangement.','benefit':'Clarifies scope.','risk':'Confirm authority.','claim_ids':[claim]}]}
                result['red_lines'] = [{'text':'Counterparty requests equipment.','claim_ids':[claim]}]
            return result, usage
        service = AnalysisService(self.path, brief_transport)
        first = service.parse(self.package())
        self.assertEqual(first['caseAnalysis']['red_lines'], [])
        self.assertEqual(len(first['caseAnalysis']['brief']['opponent_demands']), 1)
        service.parse(self.package())
        self.assertEqual(self.calls, ['document','case'])
        service.parse({**self.package(), 'context':{'our_side':'Team A','objective':'Confirm authority'}})
        self.assertEqual(self.calls, ['document','case','case'])

    def test_brief_rejects_unsupported_recommendation(self):
        def unsupported(prompt):
            result, usage = self.transport(prompt)
            if json.loads(prompt)['task'] == 'case':
                result['brief'] = {'opening':{'text':'Promise an unsupported payment.','claim_ids':[],'status':'inferred'}}
            return result, usage
        with self.assertRaisesRegex(InferenceError, 'no supporting evidence'):
            AnalysisService(self.path, unsupported).parse(self.package())

    def test_progress_reports_real_document_and_case_milestones(self):
        service = AnalysisService(self.path, self.transport)
        events = []
        service.parse(self.package(), on_progress=events.append)
        self.assertEqual([(e['type'], e['status']) for e in events], [('source','running'),('source','complete'),('case','running'),('case','complete')])
        self.assertEqual(events[1]['sourceId'], self.source['id'])
        events.clear()
        service.parse(self.package(), on_progress=events.append)
        self.assertTrue(events[1]['cacheHit'])
        self.assertTrue(events[-1]['cacheHit'])

    def test_pdf_whitespace_quotes_keep_exact_source_and_offsets(self):
        source = {**self.source, 'text': 'You represent\nTeam A. Team B needs equipment.', 'sections': []}
        result = AnalysisService(self.path, self.transport).parse(self.package(source))
        fact = result['facts'][0]
        self.assertEqual(fact['quote'], 'You represent\nTeam A.')
        self.assertEqual(source['text'][fact['quoteStart']:fact['quoteEnd']], fact['quote'])

    def test_model_version_and_scope_invalidate_cache(self):
        with patch.dict(os.environ, {'HUIT_MODEL': 'test-model', 'CACHE_SCOPE': 'project-a'}):
            AnalysisService(self.path, self.transport).parse(self.package())
        with patch.dict(os.environ, {'HUIT_MODEL': 'other-model', 'CACHE_SCOPE': 'project-a'}):
            AnalysisService(self.path, self.transport).parse(self.package())
        self.assertEqual(self.calls.count('document'), 2)

    def test_case_rejects_unknown_support(self):
        def bad_case(prompt):
            result, usage = self.transport(prompt)
            if json.loads(prompt)['task'] == 'case':
                result['red_lines'] = [{'text': 'Unsupported veto', 'claim_ids': ['missing']}]
            return result, usage
        for _ in range(2):
            with self.assertRaisesRegex(InferenceError, 'unknown evidence'):
                AnalysisService(self.path, bad_case).parse(self.package())
        self.assertEqual(self.calls, ['document', 'case'])


if __name__ == '__main__':
    unittest.main()
