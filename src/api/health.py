import threading
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from ..core import config

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Risponde solo alla rotta /health
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Costruisce la risposta di stato
            response = {
                "status": "ok",
                "service": "hermes_scheduler",
                "active_workers": config.MAX_WORKERS,
                "poll_interval_sec": config.POLL_INTERVAL
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Disabilita i noiosi log di default del server HTTP per mantenere la console pulita
        pass

def start_health_server(port=8080):
    # Avvia il server HTTP su un thread in background
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    config.logger.info(f"status=health_server_started port={port} endpoint=/health")
    
    # daemon=True fa in modo che il server muoia automaticamente quando Hermes si spegne
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server