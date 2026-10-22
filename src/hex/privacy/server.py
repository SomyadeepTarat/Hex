"""Local stdlib API for the HEX synthetic-data demo: python src/hex/privacy/server.py"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json

from pipeline import build_dashboard_payload


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/api/demo":
            self.send_error(404)
            return
        try:
            body = json.dumps(build_dashboard_payload()).encode("utf-8")
        except Exception as exc:
            body = json.dumps({"error": str(exc)}).encode("utf-8")
            self.send_response(500)
        else:
            self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    print("HEX demo data API: http://localhost:8001/api/demo")
    ThreadingHTTPServer(("127.0.0.1", 8001), Handler).serve_forever()
