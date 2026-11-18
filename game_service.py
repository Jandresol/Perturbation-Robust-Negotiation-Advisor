"""Game-builder endpoint for the frontend on scaffold/frontend-architecture.

    python3 game_service.py

Then set Pipeline settings → Game builder to http://localhost:8001/game
The posted package's facts become actions, a game, and strategies.
"""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from solver import respond

PORT = 8001


def build_response(request):
    """Build and solve the posted package. Echo its package id."""
    if not isinstance(request, dict):
        raise ValueError("POST a JSON object.")
    package = request.get("package") if isinstance(request.get("package"), dict) else request
    package_id = request.get("packageId") or package.get("id")
    if not isinstance(package_id, str) or not package_id.strip():
        raise ValueError("Request needs packageId.")
    built = respond(package, request.get("commitments") or [])
    return {
        "packageId": package_id,
        "facts": built["facts"],
        "actions": built["actions"],
        "game": built["game"],
        "strategies": built["strategies"],
    }


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "Use POST /game"})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/game":
            return self._json(404, {"error": "Use POST /game"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 25 * 1024 * 1024:
                return self._json(413, {"error": "Supply a JSON package smaller than 25 MB"})
            request = json.loads(self.rfile.read(length))
            return self._json(200, build_response(request))
        except (ValueError, json.JSONDecodeError) as err:
            return self._json(400, {"error": str(err)})


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Game builder at http://127.0.0.1:{PORT}/game")
    server.serve_forever()


if __name__ == "__main__":
    main()
