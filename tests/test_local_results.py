"""Local Save/Send of AI Fill results: same-origin guard, numbered outputs and provenance."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from PIL import Image, ImageCms

from shp_ai_fill import server as C
from winlinks import file_symlink

SRGB_ICC = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


class LocalResultTests(unittest.TestCase):
    def test_crop_result_http_route_requires_same_origin(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), C.Handler)
        worker = threading.Thread(target=server.serve_forever)
        worker.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            for origin in (None, "http://untrusted.invalid", base):
                headers = {"Content-Type": "application/json"}
                if origin:
                    headers["Origin"] = origin
                with patch.dict(C.ROUTES, {"/api/send-result": Mock(return_value={"saved": True})}):
                    request = Request(base + "/api/send-result", b"{}", headers)
                    if origin == base:
                        with urlopen(request, timeout=5) as response:
                            self.assertEqual(json.load(response), {"saved": True})
                        C.ROUTES["/api/send-result"].assert_called_once_with({})
                    else:
                        with self.assertRaises(HTTPError) as error:
                            urlopen(request, timeout=5)
                        self.assertEqual(error.exception.code, 403)
                        C.ROUTES["/api/send-result"].assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            worker.join()

    def test_selected_flattened_output_provenance_collisions_and_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "portrait.png"
            Image.new("RGB", (200, 200), (10, 20, 30)).save(source, icc_profile=SRGB_ICC)
            original = source.read_bytes()
            state = {"img": None, "seq": 0, "job": C.X.Job(), "thread": None, "imgs": {}}
            with patch.object(C, "STATE", state):
                loaded = C.api_load({"path": str(source)})
                self.assertEqual(loaded["source_kind"], "local")
                with self.assertRaisesRegex(ValueError, "generate a result first"):
                    C.api_send_result({})
                results = [{"canvas": Image.new("RGB", (240, 260), colour),
                            "layer": Image.new("RGBA", (240, 260)), "margins": (20, 30, 20, 30)}
                           for colour in ((50, 60, 70), (80, 90, 100))]
                state["job"].results = results
                state["job"].result = results[0]
                C.api_select({"index": 1})
                first = root / "portrait_shpcrop_001.png"
                file_symlink(first, source)
                with patch.object(C, "api_pc_status") as pc:
                    saved = C.api_send_result({"seq": loaded["seq"], "path": "/ignored.png"})
                    pc.assert_not_called()
                output = Path(saved["path"])
                self.assertEqual(output, root / "portrait_shpcrop_002.png")
                with Image.open(output) as image:
                    self.assertEqual(image.mode, "RGB")
                    self.assertEqual(image.size, (240, 260))
                    self.assertEqual(image.getpixel((0, 0)), (80, 90, 100))
                    self.assertNotIn("icc_profile", image.info)  # Existing Crop output is untagged RGB8.
                self.assertEqual(source.read_bytes(), original)
                next_output = C.api_send_result({})["path"]
                self.assertTrue(next_output.endswith("_003.png"))
                with self.assertRaisesRegex(ValueError, "loaded image changed"):
                    C.api_send_result({"seq": loaded["seq"] - 1})
                with patch.object(C, "running", return_value=True):
                    with self.assertRaisesRegex(ValueError, "running expansion"):
                        C.api_send_result({})
                with patch.object(C, "bridge") as bridge:
                    bridge.return_value.fetch.return_value = (source, {"name": "PC image"})
                    fetched = C.api_fetch({})
                self.assertEqual(fetched["source_kind"], "photocraft")
                state["job"].result = results[1]
                with patch.object(C, "api_pc_status", return_value={"connected": False}), \
                        patch.object(C, "write_local_result") as writer:
                    with self.assertRaisesRegex(ValueError, "disconnected"):
                        C.api_send_result({})
                    writer.assert_not_called()
                with patch.object(C, "api_pc_status", return_value={"connected": True}), \
                        patch.object(C, "api_send", return_value={"sent": True}) as send:
                    self.assertEqual(C.api_send_result({}), {"sent": True})
                    send.assert_called_once_with({})
                C.api_load({"path": str(source)})
                self.assertEqual(state["source_kind"], "local")
                self.assertIsNone(state["doc"])
                self.assertIsNone(state["job"].result)
                before = state.copy()
                with self.assertRaisesRegex(ValueError, "not an image"):
                    C.api_load({"path": str(root / "absent.png")})
                self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
