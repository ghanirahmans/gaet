import json
import unittest
from http.server import HTTPServer
from threading import Thread
from urllib.request import urlopen, Request
from dashboard.server import DashboardHandler, serve


class TestDashboardServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 9999), DashboardHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_get_index(self):
        res = urlopen('http://127.0.0.1:9999/')
        self.assertEqual(res.status, 200)
        body = res.read().decode('utf-8')
        self.assertIn('gaet — Database Operations Dashboard', body)

    def test_api_status(self):
        res = urlopen('http://127.0.0.1:9999/api/status')
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode('utf-8'))
        self.assertIn('tables', data)

    def test_api_snapshots(self):
        res = urlopen('http://127.0.0.1:9999/api/snapshots')
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode('utf-8'))
        self.assertIn('snapshots', data)

    def test_api_logs(self):
        res = urlopen('http://127.0.0.1:9999/api/logs')
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode('utf-8'))
        self.assertIn('logs', data)

    def test_api_config(self):
        res = urlopen('http://127.0.0.1:9999/api/config')
        self.assertEqual(res.status, 200)
        data = json.loads(res.read().decode('utf-8'))
        self.assertIn('config', data)


if __name__ == '__main__':
    unittest.main()
