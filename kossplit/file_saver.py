"""Save exported reports to a location the user chooses.

Android uses the system "save as" screen (Storage Access Framework), so the user can pick
Downloads, Documents, Google Drive, or any other provider without a storage permission.
Computers copy the finished file into a folder picked inside the app.
"""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path
from typing import Callable

REQUEST_SAVE = 4713
CHUNK_SIZE = 64 * 1024
MIME_TYPES = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


def report_filename(extension: str, today: date | None = None) -> str:
    return f"kossplit-{(today or date.today()).isoformat()}.{extension}"


def mime_type(extension: str) -> str:
    return MIME_TYPES.get(extension.lower().lstrip("."), "application/octet-stream")


def clean_filename(name: str, extension: str) -> str:
    """A safe file name that always ends with the report extension."""
    suffix = "." + extension.lower().lstrip(".")
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name).strip()
    if cleaned.lower().endswith(suffix):
        cleaned = cleaned[: -len(suffix)]
    cleaned = cleaned.strip(" .")
    if not cleaned:
        raise ValueError("Nama file tidak boleh kosong")
    return cleaned + suffix


def copy_to_folder(source: Path, folder: Path, filename: str) -> Path:
    """Copy a finished report into a folder chosen on a computer."""
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Folder tidak ditemukan: {folder}")
    destination = folder / filename
    shutil.copyfile(source, destination)
    return destination


SavedCallback = Callable[[str, object], None]


class AndroidDocumentSaver:
    """Opens Android's save screen and writes the report into the chosen document."""

    def __init__(self, autoclass=None, activity_events=None, post=None):
        if autoclass is None:
            from jnius import autoclass
        if activity_events is None:
            from android import activity as activity_events
        if post is None:
            from kivy.clock import Clock

            def post(callback, *args):
                Clock.schedule_once(lambda *_: callback(*args), 0)

        self.autoclass = autoclass
        self.activity_events = activity_events
        self.post = post
        self.Intent = autoclass("android.content.Intent")
        self.PythonActivity = autoclass("org.kivy.android.PythonActivity")
        self.Activity = autoclass("android.app.Activity")
        self._pending: dict | None = None
        self._bound = False

    def save(
        self,
        data: bytes,
        filename: str,
        mime: str,
        on_saved: SavedCallback,
        on_cancel: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self._pending = {
            "data": data,
            "filename": filename,
            "on_saved": on_saved,
            "on_cancel": on_cancel,
            "on_error": on_error,
        }
        intent = self.Intent(self.Intent.ACTION_CREATE_DOCUMENT)
        intent.addCategory(self.Intent.CATEGORY_OPENABLE)
        intent.setType(mime)
        intent.putExtra(self.Intent.EXTRA_TITLE, filename)
        if not self._bound:
            self.activity_events.bind(on_activity_result=self._on_activity_result)
            self._bound = True
        try:
            self.PythonActivity.mActivity.startActivityForResult(intent, REQUEST_SAVE)
        except Exception as error:
            self._finish()
            self.post(on_error, f"Pemilih lokasi tidak dapat dibuka: {error}")

    def _finish(self) -> dict | None:
        pending, self._pending = self._pending, None
        if self._bound:
            self.activity_events.unbind(on_activity_result=self._on_activity_result)
            self._bound = False
        return pending

    def _on_activity_result(self, request_code, result_code, intent):
        if request_code != REQUEST_SAVE:
            return
        pending = self._finish()
        if pending is None:
            return
        uri = intent.getData() if intent is not None else None
        if result_code != self.Activity.RESULT_OK or uri is None:
            self.post(pending["on_cancel"])
            return
        try:
            self.write(uri, pending["data"])
        except Exception as error:
            self.post(pending["on_error"], f"Laporan gagal disimpan: {error}")
            return
        self.post(pending["on_saved"], self.display_name(uri, pending["filename"]), uri)

    def _resolver(self):
        return self.PythonActivity.mActivity.getContentResolver()

    def write(self, uri, data: bytes) -> None:
        resolver = self._resolver()
        try:
            stream = resolver.openOutputStream(uri, "wt")
        except Exception:  # Some providers do not support truncate mode
            stream = resolver.openOutputStream(uri, "w")
        if stream is None:
            raise OSError("lokasi tidak dapat ditulis")
        try:
            for start in range(0, len(data), CHUNK_SIZE):
                chunk = data[start : start + CHUNK_SIZE]
                stream.write(chunk, 0, len(chunk))
            stream.flush()
        finally:
            stream.close()

    def display_name(self, uri, fallback: str) -> str:
        """The name the provider gave the file; it may add (1) when the name was taken."""
        cursor = None
        try:
            cursor = self._resolver().query(uri, ["_display_name"], None, None, None)
            if cursor is not None and cursor.moveToFirst():
                return cursor.getString(0) or fallback
        except Exception:
            pass
        finally:
            if cursor is not None:
                cursor.close()
        return fallback

    def open(self, uri, mime: str) -> bool:
        intent = self.Intent(self.Intent.ACTION_VIEW)
        intent.setDataAndType(uri, mime)
        intent.addFlags(self.Intent.FLAG_GRANT_READ_URI_PERMISSION | self.Intent.FLAG_ACTIVITY_NEW_TASK)
        try:
            self.PythonActivity.mActivity.startActivity(intent)
            return True
        except Exception:
            return False
