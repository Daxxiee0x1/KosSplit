"""Receipt scanning.

Android: Google ML Kit Document Scanner opens the camera with edge detection
and gallery import, then ML Kit Text Recognition reads the image on device.
Both are Java libraries called from Python through Pyjnius.

Desktop: an image file is read with Tesseract through pytesseract when it is
installed. Pasting receipt text works everywhere as a fallback.
"""

from __future__ import annotations

import threading
from typing import Callable

from kivy.clock import mainthread
from kivy.utils import platform

from .receipt_parser import rows_from_boxes

REQUEST_SCAN = 4711
REQUEST_PICK = 4712

TextCallback = Callable[[str], None]
ErrorCallback = Callable[[str], None]


class ReceiptScanner:
    def __init__(self, on_text: TextCallback, on_error: ErrorCallback):
        self._on_text = on_text
        self._on_error = on_error

    @property
    def is_android(self) -> bool:
        return platform == "android"

    @mainthread
    def deliver(self, text: str) -> None:
        if text.strip():
            self._on_text(text)
        else:
            self._on_error("Teks struk tidak terbaca. Coba foto lebih terang dan lurus.")

    @mainthread
    def fail(self, message: str) -> None:
        self._on_error(message)

    def scan_camera(self) -> None:
        if not self.is_android:
            self.fail("Kamera hanya tersedia pada APK Android. Pilih file gambar.")
            return
        _AndroidBridge.get(self).scan_camera()

    def pick_gallery(self) -> None:
        if not self.is_android:
            self.fail("Galeri Android hanya tersedia pada APK.")
            return
        _AndroidBridge.get(self).pick_gallery()

    def read_file(self, path: str) -> None:
        """Desktop OCR in a worker thread so the UI does not freeze."""

        def work():
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                self.fail(
                    "OCR desktop memerlukan Tesseract. Jalankan: pip install pytesseract pillow, "
                    "lalu pasang aplikasi Tesseract OCR. Alternatifnya, tempel teks struk."
                )
                return
            try:
                image = Image.open(path)
                try:
                    text = pytesseract.image_to_string(image, lang="ind+eng", config="--psm 6")
                except pytesseract.TesseractError:
                    text = pytesseract.image_to_string(image, config="--psm 6")
                self.deliver(text)
            except Exception as error:  # Tesseract binary missing or unreadable image
                self.fail(f"Gagal membaca gambar: {error}")

        threading.Thread(target=work, daemon=True).start()


class _AndroidBridge:
    """Holds Java listeners so they are not garbage collected mid-task."""

    _instance: "_AndroidBridge | None" = None

    @classmethod
    def get(cls, scanner: ReceiptScanner) -> "_AndroidBridge":
        if cls._instance is None:
            cls._instance = cls()
        cls._instance.scanner = scanner
        return cls._instance

    def __init__(self):
        from android import activity
        from jnius import PythonJavaClass, autoclass, cast, java_method

        self.scanner: ReceiptScanner | None = None
        self.activity_events = activity
        self.autoclass = autoclass
        self.cast = cast
        self.PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self.Activity = autoclass("android.app.Activity")
        self.Intent = autoclass("android.content.Intent")
        self._keep: list = []
        self._bound = False

        class SuccessListener(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnSuccessListener"]
            __javacontext__ = "app"

            def __init__(self, callback):
                super().__init__()
                self.callback = callback

            @java_method("(Ljava/lang/Object;)V")
            def onSuccess(self, result):
                self.callback(result)

        class FailureListener(PythonJavaClass):
            __javainterfaces__ = ["com/google/android/gms/tasks/OnFailureListener"]
            __javacontext__ = "app"

            def __init__(self, callback):
                super().__init__()
                self.callback = callback

            @java_method("(Ljava/lang/Exception;)V")
            def onFailure(self, error):
                self.callback(error)

        self.SuccessListener = SuccessListener
        self.FailureListener = FailureListener

    def _listen(self, task, on_success, failure_message: str) -> None:
        def on_failure(error):
            detail = error.getMessage() if error is not None else ""
            self.scanner.fail(f"{failure_message}. {detail or ''}".strip())

        success = self.SuccessListener(on_success)
        failure = self.FailureListener(on_failure)
        self._keep = [success, failure]
        task.addOnSuccessListener(success)
        task.addOnFailureListener(failure)

    def _bind(self) -> None:
        if not self._bound:
            self.activity_events.bind(on_activity_result=self._on_activity_result)
            self._bound = True

    def _unbind(self) -> None:
        if self._bound:
            self.activity_events.unbind(on_activity_result=self._on_activity_result)
            self._bound = False

    def scan_camera(self) -> None:
        try:
            prefix = "com.google.mlkit.vision.documentscanner."
            Options = self.autoclass(prefix + "GmsDocumentScannerOptions")
            Builder = self.autoclass(prefix + "GmsDocumentScannerOptions$Builder")
            Scanning = self.autoclass(prefix + "GmsDocumentScanning")
            options = (
                Builder()
                .setGalleryImportAllowed(True)
                .setPageLimit(1)
                .setScannerMode(Options.SCANNER_MODE_BASE)
                .build()
            )
            scanner = Scanning.getClient(options)
            task = scanner.getStartScanIntent(self.PythonActivity.mActivity)
            self._listen(task, self._launch_scanner, "Pemindai kamera tidak tersedia")
        except Exception as error:
            self.scanner.fail(f"Pemindai kamera tidak tersedia: {error}. Pilih dari galeri.")

    def _launch_scanner(self, sender) -> None:
        self._bind()
        intent_sender = self.cast("android.content.IntentSender", sender)
        self.PythonActivity.mActivity.startIntentSenderForResult(
            intent_sender, REQUEST_SCAN, None, 0, 0, 0
        )

    def pick_gallery(self) -> None:
        intent = self.Intent(self.Intent.ACTION_GET_CONTENT)
        intent.setType("image/*")
        intent.addCategory(self.Intent.CATEGORY_OPENABLE)
        self._bind()
        self.PythonActivity.mActivity.startActivityForResult(intent, REQUEST_PICK)

    def _on_activity_result(self, request_code, result_code, data):
        if request_code not in (REQUEST_SCAN, REQUEST_PICK):
            return
        self._unbind()
        if result_code != self.Activity.RESULT_OK or data is None:
            self.scanner.fail("Pemindaian dibatalkan.")
            return
        try:
            if request_code == REQUEST_SCAN:
                prefix = "com.google.mlkit.vision.documentscanner."
                Result = self.autoclass(prefix + "GmsDocumentScanningResult")
                result = Result.fromActivityResultIntent(data)
                pages = result.getPages() if result is not None else None
                if pages is None or pages.size() == 0:
                    self.scanner.fail("Tidak ada halaman yang dipindai.")
                    return
                page = self.cast(prefix + "GmsDocumentScanningResult$Page", pages.get(0))
                uri = page.getImageUri()
            else:
                uri = data.getData()
            self._recognize(uri)
        except Exception as error:
            self.scanner.fail(f"Gambar tidak dapat dibuka: {error}")

    def _recognize(self, uri) -> None:
        InputImage = self.autoclass("com.google.mlkit.vision.common.InputImage")
        TextRecognition = self.autoclass("com.google.mlkit.vision.text.TextRecognition")
        Options = self.autoclass("com.google.mlkit.vision.text.latin.TextRecognizerOptions")
        image = InputImage.fromFilePath(self.PythonActivity.mActivity, uri)
        recognizer = TextRecognition.getClient(Options.DEFAULT_OPTIONS)
        self._listen(recognizer.process(image), self._read_text, "Teks struk tidak terbaca")

    def _read_text(self, result) -> None:
        prefix = "com.google.mlkit.vision.text.Text"
        text = self.cast(prefix, result)
        boxes = []
        blocks = text.getTextBlocks()
        for block_index in range(blocks.size()):
            block = self.cast(prefix + "$TextBlock", blocks.get(block_index))
            lines = block.getLines()
            for line_index in range(lines.size()):
                line = self.cast(prefix + "$Line", lines.get(line_index))
                box = line.getBoundingBox()
                if box is None:
                    continue
                boxes.append((line.getText(), box.left, box.top, box.right, box.bottom))
        self.scanner.deliver(rows_from_boxes(boxes) if boxes else text.getText())
