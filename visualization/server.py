"""Simple HTTP server that serves the mind map and graph data."""

import http.server
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WEB_DIR = Path(__file__).resolve().parent / "web" / "public"


class GraphHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self):
        if self.path.startswith("/data/graph.json"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            graph_path = DATA_DIR / "graph.json"
            if graph_path.exists():
                self.wfile.write(graph_path.read_bytes())
            else:
                self.wfile.write(b'{"nodes":[],"edges":[]}')
        else:
            super().do_GET()

    def log_message(self, format, *args):
        pass  # Quiet logging


def serve(port: int = 8420) -> None:
    server = http.server.HTTPServer(("localhost", port), GraphHandler)
    print(f"Mind map: http://localhost:{port}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    serve()
