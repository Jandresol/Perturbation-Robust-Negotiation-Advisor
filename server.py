"""Local static app plus HUIT inference API. Run: python3 server.py"""
import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from backend.inference import AnalysisService, InferenceError, load_env

ROOT = Path(__file__).resolve().parent
load_env(ROOT / '.env')


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Local development must not mix scripts from different app revisions.
        if not self.path.startswith('/api/'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def json_response(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def send_head(self):
        path = unquote(urlsplit(self.path).path)
        target = Path(self.translate_path(path)).resolve()
        if any(p.startswith('.') for p in Path(path).parts) or not target.is_relative_to(ROOT) or target.suffix in ['.py', '.sqlite', '.db']:
            self.send_error(404); return None
        return super().send_head()

    def list_directory(self, path):
        self.send_error(404); return None

    def do_GET(self):
        if self.path == '/api/config':
            return self.json_response(200, self.server.analysis.config())
        if self.path.startswith('/api/'):
            return self.json_response(404, {'error': 'Unknown API endpoint'})
        super().do_GET()

    def do_POST(self):
        if urlsplit(self.path).path != '/api/sources/parse':
            return self.json_response(404, {'error': 'Unknown API endpoint'})
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.json_response(403, {'error': 'Only same-origin requests are accepted'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 25 * 1024 * 1024:
                return self.json_response(413, {'error': 'Supply a JSON package smaller than 25 MB'})
            data = json.loads(self.rfile.read(length))
            package = data.get('package', data)
            if 'application/x-ndjson' in self.headers.get('Accept', ''):
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.end_headers()
                self.close_connection = True
                def emit(event):
                    try:
                        self.wfile.write((json.dumps(event) + '\n').encode())
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        # Finish this paid request and retain output even if the browser closes.
                        pass
                try:
                    result = self.server.analysis.parse(package, on_progress=emit)
                    emit({'type':'result', 'result':result})
                except InferenceError as exc:
                    emit({'type':'error', 'error':str(exc)})
                except Exception:
                    emit({'type':'error', 'error':'Source parsing failed. Completed and paid outputs are retained locally.'})
                return
            result = self.server.analysis.parse(package)
            self.json_response(200, result)
        except InferenceError as exc:
            self.json_response(502, {'error': str(exc)})
        except (ValueError, TypeError, KeyError, AttributeError):
            self.json_response(400, {'error': 'Invalid source package or JSON'})
        except Exception:
            self.json_response(500, {'error': 'Source parsing failed. Existing cached outputs are retained.'})


def make_server(port=8000, database=None):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.analysis = AnalysisService(database or ROOT / '.data' / 'analysis.sqlite')
    return server


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    server = make_server(args.port)
    print(f'Negotiation Advisor: http://localhost:{args.port}', flush=True)
    server.serve_forever()
