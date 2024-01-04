from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
from socketserver import BaseServer
import json
import urllib.parse as urlparse


class Authenticator:
    local_url: str = "localhost"
    local_port: int = 8000
    remote_url: str = None
    server_thread: threading.Thread = None
    server: HTTPServer = None

    def __init__(
            self,
            local_url: str,
            remote_url: str) -> None:
        self.local_url = local_url
        self.remote_url = remote_url

    def start(self):
        def get_auth_request_handler(socket, client_address, server) -> BaseHTTPRequestHandler:
            print(client_address, server)
            request_handler = AuthenticatorRequestHandler(self, socket, client_address, server)
            request_handler.authenticator = self
            return request_handler

        server_address = (self.local_url, self.local_port)
        self.server = ThreadingHTTPServer(server_address, get_auth_request_handler)
        print('starting')
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()
        print('server thread started')
        print(self.server_thread)

    def end(self):
        self.server.shutdown()
        self.server_thread.join()


class AuthenticatorRequestHandler(BaseHTTPRequestHandler):

    authenticator: Authenticator = None

    def __init__(self,
                 authenticator: Authenticator,
                 request,
                 client_address,
                 server: BaseServer):
        self.authenticator = authenticator
        super().__init__(request, client_address, server)

    def do_GET(self):
        print(json.dumps(json.load(self.rfile)))

        parsed_path = urlparse.urlparse(self.path)
        self.start_authentication()
        self.send_response(200)

        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write("RESPONSE".encode("utf-8"))

    def start_authentication(self):
        print(self.authenticator.remote_url)
        pass
