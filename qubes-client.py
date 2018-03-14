"""
This implements a dispatcher which listens to localhost:8550, and proxies
requests via qrexec to the service qubes.EthSign on a target domain
"""

import http.server
import socketserver
import subprocess

PORT=8550
TARGET_DOMAIN= 'debian-work'

class Dispatcher(http.server.BaseHTTPRequestHandler):
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        output = subprocess.check_output(['/usr/lib/qubes/qrexec-client','-d',TARGET_DOMAIN],
             stdin = post_data)
        self.wfile.write(output)

with socketserver.TCPServer(("",PORT), Dispatcher) as httpd:
    print("Serving at port", PORT)
    httpd.serve_forever()
