from http.server import HTTPServer, SimpleHTTPRequestHandler
import os

SWF_DIR = os.path.join(os.path.dirname(__file__), "public")

class SWFHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SWF_DIR, **kwargs)

    def end_headers(self):
        # Allow Flash to load files from this server
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        print(f"[HTTP] {format % args}")

def start_http_server(host, http_port):
    server = HTTPServer((host, http_port), SWFHandler)
    print(f"HTTP server listening on {host}:{http_port}")
    server.serve_forever()