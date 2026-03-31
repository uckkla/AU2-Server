from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import logging

SWF_DIR = os.path.join(os.path.dirname(__file__), "..", "public")
logger = logging.getLogger(__name__)

class SWFHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SWF_DIR, **kwargs)

    def end_headers(self):
        # Allow Flash to load files from this server
        self.send_header("Access-Control-Allow-Origin", "*")
        if self.path == "/config.xml":
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        logger.debug(f"[HTTP] {format % args}")

def start_http_server(host, http_port):
    server = HTTPServer((host, http_port), SWFHandler)
    logger.info(f"HTTP server listening on {host}:{http_port}")
    server.serve_forever()