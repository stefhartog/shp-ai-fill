"""In-memory PhotoCraft automation fake shared by the bridge and Patch Fill tests."""

import cv2
from PIL import Image, ImageCms

from shp_ai_fill.shared.photocraft import ControlError


class FakePhotoCraft:
    def __init__(self, bridge, headless=False, fail_copy=False, retry_mask=False):
        self.bridge = bridge
        self.headless = headless
        self.fail_copy = fail_copy
        self.retry_mask = retry_mask
        self.calls = []
        self.active = 1
        self.documents = [{"index": 1, "name": "portrait:one.png", "width": 64, "height": 48}]
        self.files = []
        self.history = ["Original"]
        self.icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        self.file_profiles = []

    def session(self):
        return {"active": self.active, "documents": self.documents.copy()}

    def call(self, method, **params):
        self.calls.append((method, params))
        if method == "ui.inspect":
            if self.headless:
                raise ControlError("unknown method: ui.inspect")
            return {"session": self.session()}
        if method == "session.list":
            return self.session()
        if method in ("app.save", "doc.save"):
            Image.new("RGB", (64, 48), "red").save(self.bridge.exchange / params["path"], icc_profile=self.icc)
        if method in ("app.open", "doc.open"):
            filename = self.bridge.read_root / params["path"]
            self.files.append(cv2.imread(str(filename), cv2.IMREAD_UNCHANGED))
            with Image.open(filename) as image:
                self.file_profiles.append(image.info.get("icc_profile"))
            self.active = max(d["index"] for d in self.documents) + 1
            self.documents.append({"index": self.active, "name": filename.name})
        return {}

    def run(self, command, **params):
        self.calls.append((command, params))
        if command == "document.activate":
            self.active = params["document"]
        if command == "image.duplicate":
            self.active = max(d["index"] for d in self.documents) + 1
            self.documents.append({"index": self.active, "name": params["name"]})
        if command == "file.close":
            self.documents = [d for d in self.documents if d["index"] != params["document"]]
        if command == "layer.list":
            return {"layers": [{"id": self.active * 10}]}
        if command == "document.inspect":
            return {"history": self.history.copy()}
        if command == "select.loadSelection" and self.retry_mask:
            self.retry_mask = False
            raise ControlError("selection was cleared")
        if command == "layer.copyToDocument":
            if self.fail_copy:
                raise ControlError("copy failed")
            self.history += ["Resize", "Layer"]
            return {"layers": [99]}
        if command == "history.newSnapshot":
            return {"snapshot": 7}
        return {}


