"""AI Fill PhotoCraft send contracts against an in-memory fake. Shared transport tests live upstream."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from fake_photocraft import FakePhotoCraft
from shp_ai_fill.photocraft_bridge import Bridge
from shp_ai_fill.shared.photocraft import ControlError


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bridge(self, **fake_options):
        b = Bridge(port=1, token_file=self.root / "no-token", exchange=self.root / "exchange", read_root=self.root)
        b.config_dir = self.root / "config"
        b.client = FakePhotoCraft(b, **fake_options)
        return b

    def test_open_uses_absolute_path_in_gui_and_relative_when_headless(self):
        for headless in (False, True):
            with self.subTest(headless=headless):
                b = self.bridge(headless=headless)
                b.headless = headless
                b.client.calls.clear()
                rel = "scratch.png"
                Image.new("RGB", (4, 4)).save(b.exchange / rel)
                b._open(rel)
                method, params = next(c for c in b.client.calls if c[0] in ("app.open", "doc.open"))
                if headless:
                    self.assertEqual((method, params["path"]), ("doc.open", "exchange/scratch.png"))
                else:
                    self.assertEqual((method, params["path"]), ("app.open", str(b.exchange / rel)))

    def test_open_refuses_exchange_outside_read_root(self):
        b = self.bridge()
        b.read_root = self.root / "elsewhere"
        with self.assertRaises(ControlError):
            b._open("scratch.png")
        self.assertFalse(any(c[0] == "app.open" for c in b.client.calls))

    def test_crop_signed_margins_and_grouped_undo(self):
        b = self.bridge()
        layer = np.zeros((58, 60, 4), np.uint8)
        b.send_expand(layer, b.client.documents[0], (-4, 5, 0, 5))
        self.assertIn(("image.crop", {"x": 4, "y": -5, "width": 60, "height": 58}), b.client.calls)
        self.assertIn(("history.selectSnapshot", {"snapshot": 7}), b.client.calls)
        self.assertFalse(any(c.startswith("select.") or "layerMask" in c for c, p in b.client.calls))
        self.assertEqual(b.client.active, 1)
        self.assertEqual(list(b.exchange.iterdir()), [])

    def test_failed_send_cleans_scratch_and_reports_error(self):
        b = self.bridge(fail_copy=True)
        with self.assertRaisesRegex(ControlError, "copy failed"):
            b.send_expand(np.zeros((58, 64, 4), np.uint8), b.client.documents[0], (0, 5, 0, 5))
        self.assertEqual(b.client.active, 1)
        self.assertEqual(len(b.client.documents), 1)
        self.assertEqual(list(b.exchange.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
