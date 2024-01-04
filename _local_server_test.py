import unittest

import requests

from _publish_test import API_URL
from lxd.local_server import *


class TestStartServer(unittest.TestCase):
    authenticator: Authenticator = None

    def setUp(self):
        self.authenticator = Authenticator('localhost', API_URL)
        self.authenticator.start()

    def tearDown(self):
        self.authenticator.end()

    def test_get(self):
        print("test_serve_page")
        response = requests.get(f'http://{self.authenticator.local_url}:{self.authenticator.local_port}')
        print("Response received")
        print(response)
        self.assertEqual(response.status_code, 200)

    def test_authenticate(self):
        print("test_authenticate")
        response = requests.post(
            self.authenticator.remote_url,
            data={
                'username': 'test',
                'password': '<PASSWORD>'
            })