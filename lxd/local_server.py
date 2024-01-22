import random
import string
import urllib.parse
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
import ssl
from socketserver import BaseServer
import json
import urllib.parse as urlparse
from typing import Callable

import OpenSSL


# This is a doomed and deeply flawed implementation as it spins up a server and also contains client methods.
class Authenticator:
    def __init__(
            self,
            client_id: int,
            local_url: str,
            local_port: int,
            remote_url: str,
            authenticate_callback: Callable = None):

        self.server_thread = None
        self.server = None

        self.authenticate_callback = authenticate_callback
        self.local_url = local_url
        self.local_port: int = local_port
        self.client_id = client_id
        self.remote_url = remote_url

        self.state = ''.join([random.choice(string.ascii_letters) for i in range(0, 64)])


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
        # self.server.socket = (

        #    ssl.wrap_socket(self.server.socket, server_side=True, certfile='selfsigned.crt', keyfile='private.key'))
        self.server_thread.start()
        print('server thread started')
        print(self.server_thread)

    def end(self):
        self.server.shutdown()
        self.server_thread.join()

    def get_redirect_url(self) -> str:
        redirect_uri = f"http://{self.local_url}:{self.local_port}/oauth2"
        print(redirect_uri)
        url = urlparse.urlunparse([
            'https',
            'unity.test.instructure.com',
            'login/oauth2/auth',
            None,
            urlparse.urlencode({
                'state': self.state,
                'client_id': self.client_id,
                'response_type': 'code',
                'redirect_uri': redirect_uri
            }),
            None
        ])
        print(url)
        return str(url)

    def redirect(self, callback):
        url = self.remote_url
        webbrowser.open(self.get_redirect_url())
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
        parsed_path = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed_path.query)
        print(query)
        self.send_response(200)
        self.authenticator.finish_authentication(query)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
