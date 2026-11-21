"""AI Fill watch-folder import: target checks, retry after a failed match, and inbox cleanup."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from shp_ai_fill import server as C
from shp_ai_fill.shared.watch_folder import WatchFolder


class CropWatchTests(unittest.TestCase):
    def test_crop_inbox_separation_target_failure_retry_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skin, crop = root / "watchfolder", root / "watchfolder_crop"
            skin.mkdir(); crop.mkdir()
            pixels = cv2.imencode(".png", np.random.default_rng(1).integers(0, 256, (96, 128, 3), np.uint8))[1].tobytes()
            (skin / "skin.png").write_bytes(pixels)
            source = crop / "crop.png"
            source.write_bytes(pixels)
            now = [0]
            watcher = WatchFolder(crop, root / "retained", clock=lambda:now[0])
            self.addCleanup(watcher.close)
            watcher.status(); now[0] = 3
            token = watcher.status()["token"]
            handler = object.__new__(C.Handler)
            handler.server = SimpleNamespace(watch_folder=watcher)
            state = {"img":None,"seq":0,"job":C.X.Job(),"thread":None,"imgs":{}}
            target = {"document":{"name":"Crop.psd","index":1}, "identity":{
                "id":"crop-doc","revision":1,"width":999,"height":96}}
            with patch.object(C,"STATE",state), patch.object(C,"capture_target",return_value=target):
                with self.assertRaisesRegex(ValueError,"export size"):
                    handler.load_watch_image({"token":token})
                self.assertIsNone(state["img"])
                self.assertTrue(source.exists())
                target["identity"]["width"] = 128
                loaded = handler.load_watch_image({"token":token})
                self.assertTrue(loaded["watch_cleanup"])
                self.assertEqual(loaded["source_kind"],"photocraft")
                self.assertEqual(state["doc"],target["document"])
                self.assertEqual(loaded["width"],128)
                self.assertTrue(Path(state["path"]).is_file())
                self.assertFalse(source.exists())
                self.assertTrue((skin / "skin.png").exists())
                self.assertEqual(handler.load_watch_image({"token":token}),{"skipped":True})


if __name__ == "__main__":
    unittest.main()
