import unittest

from fastapi.testclient import TestClient

from demo_api import app


class DemoApiRouteTests(unittest.TestCase):
    def test_demo_page_supports_head(self) -> None:
        response = TestClient(app).head("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "")


if __name__ == "__main__":
    unittest.main()
