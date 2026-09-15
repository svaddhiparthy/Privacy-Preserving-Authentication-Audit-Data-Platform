from pathlib import Path
from unittest import TestCase


class PublicIdentitySurfaceTests(TestCase):
    def test_demo_uses_central_public_identity(self) -> None:
        demo = (Path(__file__).resolve().parents[1] / "docs" / "demo.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('fetch("/data/site-content.json"', demo)
        self.assertIn("data-public-display-name", demo)
        self.assertNotIn("Surya Vaddhiparthy", demo)
        self.assertNotIn("github.com/vaddhiparthy", demo)
