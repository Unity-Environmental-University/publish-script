import asyncio
import unittest

import requests

from lxd.local_server import *


constants = json.load(open('constants_test.json'))


class TestStartServer(unittest.IsolatedAsyncioTestCase):
    authenticator: Authenticator = None

    def setUp(self):
        client_id = constants['client_id']
        self.assertIsNotNone(client_id)
        self.authenticator = Authenticator(
            client_id=client_id,
            local_url="localhost",
            local_port=8000,
            remote_url='https://unity.test.instructure.com'
        )
        self.authenticator.start()

    def tearDown(self):
        self.authenticator.end()

    def test_get(self):
        print("test_serve_page")
        response = requests.get(f'http://{self.authenticator.local_url}:{self.authenticator.local_port}')
        print("Response received")
        print(response)
        self.assertEqual(response.status_code, 200)

    async def test_authenticate(self):
        print("test_authenticate")
        loop = asyncio.get_event_loop()
        future = loop.create_future()

        def callback(userdata=None):
            loop.call_soon_threadsafe(future.set_result, userdata)

        self.authenticator.redirect(callback)

        await future




