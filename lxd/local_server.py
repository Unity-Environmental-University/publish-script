import random
import string
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
from socketserver import BaseServer
import json
import urllib.parse as urlparse
from typing import Callable

import OpenSSL


# This is a doomed and deeply flawed implementation as it spins up a server and also contains client methods.
class Authenticator:
    local_url: str = "localhost"
    local_port: int = 8000
    remote_url: str = None
    state: str = ''.join([random.choice(string.ascii_letters) for i in range(0, 64)])
    server_thread: threading.Thread = None
    server: HTTPServer = None
    client_id: int = None
    authenticate_callback: Callable = None

    def __init__(
            self,
            client_id: int,
            local_url: str,
            remote_url: str) -> None:
        self.local_url = local_url
        self.client_id = client_id
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

    def getRedirectUrl(self) -> str:
        url = urlparse.urlunparse([
            'https',
            'unity.test.instructure.com',
            'login/oauth2/auth',
            None,
            urlparse.urlencode({
                'state': self.state,
                'client_id': self.client_id,
                'response_type': 'code',
                'redirect_uri': "http://localhost:8000/oauth2response"
            }),
            None
        ])
        return str(url)

    def redirect(self, callback):
        url = self.remote_url
        webbrowser.open(self.getRedirectUrl())
        self.authenticate_callback = callback

    def finish_authentication(self, query):
        code = query.get('code')
        print(code)

        if self.authenticate_callback is not None:
            self.authenticate_callback(query)
            self.authenticate_callback = None


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
        print("request received...")
        # print(json.dumps(json.load(self.rfile)))
        parsed_path = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed_path.query)
        print(query)
        self.send_response(200)
        self.authenticator.finish_authentication(query)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
