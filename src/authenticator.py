import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from ssl import PROTOCOL_TLS_SERVER, SSLContext

import tempfile
from pathlib import Path

from OpenSSL.crypto import (
    FILETYPE_PEM,
    TYPE_RSA,
    X509,
    PKey,
    dump_certificate,
    dump_privatekey
)


# credit: https://realpython.com/python-http-server/
class SelfSignedCertificate:
    host: str = "0.0.0.0"
    bits: int = 2048
    country: str = "US"
    state: str = "Maine"
    locality: str = "New Gloucester"
    organization: str = "Unity Environmental University"
    organizational_unit: str = "LXD"
    serial_number: int = 1
    expires_on: int = 365 * 24 * 60 * 60


class Authenticator:
    def __init__(self, self_url="http://localhost:8000"):
        self.self_url = self_url

