import asyncio
import unittest
import requests

from lxd.local_server import *
from _publish_test import API_URL

class TestStartServer(unittest.TestCase):
    authenticator: Authenticator = None

    def setUp(self):
        self.authenticator = Authenticator('localhost', API_URL)
        self.authenticator.start()

    def tearDown(self):
        self.authenticator.end()

    def test_serve_page(self):
        print("test_serve_page")
        response = requests.get(f'http://{self.authenticator.local_url}:{self.authenticator.local_port}')
        print("Response received")
        print(response)
        self.assertEqual(response.status_code, 200)
