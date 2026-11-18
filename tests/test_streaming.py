import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path
from server import make_server

class StreamingTests(unittest.TestCase):
    def test_streamed_source_and_case_events_then_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            server = make_server(0, Path(tmp) / 'test.sqlite')
            calls = []
            def transport(prompt):
                data = json.loads(prompt)
                calls.append(data['task'])
                if data['task'] == 'document':
                    return {'document_type':'instructions','summary':'Our role.','tags':[],'entities':[],'represented_side':'A','claims':[{'text':'We represent A.','quote':'You represent A.','attribution':'instructions','modality':'asserted','category':'context','conditions':[]}],'arguments':[],'limitations':[]}, (10,10)
                return {'title':'Test case','summary':'Test summary','our_side':'A','opponent':None,'objective':None,'outside_option':None,'red_lines':[],'issues':[]}, (10,10)
            server.analysis.transport = transport
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                for attempt in range(2):
                    request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/sources/parse',data=json.dumps({'package':{'id':'p','sources':[{'id':'s','title':'Role','text':'You represent A.','category':'role_card'}]}}).encode(),headers={'Content-Type':'application/json','Accept':'application/x-ndjson'})
                    with urllib.request.urlopen(request, timeout=5) as response:
                        self.assertIn('application/x-ndjson', response.headers['Content-Type'])
                        events = [json.loads(line) for line in response]
                    self.assertEqual([e['type'] for e in events], ['source','source','case','case','result'])
                    self.assertEqual(events[1]['status'], 'complete')
                    self.assertEqual(events[-1]['result']['facts'][0]['sourceId'], 's')
                    if attempt:
                        self.assertTrue(events[1]['cacheHit'])
                self.assertEqual(calls, ['document','case'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
