from datetime import date

import pytest

from kossplit.database import Database
from kossplit.exporter import export_excel, export_pdf
from kossplit.file_saver import (
    CHUNK_SIZE,
    REQUEST_SAVE,
    AndroidDocumentSaver,
    clean_filename,
    copy_to_folder,
    mime_type,
    report_filename,
)

RESULT_OK, RESULT_CANCELED = -1, 0


def test_report_filename_and_mime_types():
    assert report_filename("xlsx", date(2026, 11, 3)) == "kossplit-2026-11-03.xlsx"
    assert mime_type("pdf") == "application/pdf"
    assert mime_type("xlsx") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("Laporan November", "Laporan November.xlsx"),
        ("Laporan November.xlsx", "Laporan November.xlsx"),
        ("Laporan.XLSX", "Laporan.xlsx"),
        ("  kos/bulan:11?  ", "kosbulan11.xlsx"),
    ],
)
def test_clean_filename_keeps_extension_and_removes_invalid_characters(typed, expected):
    assert clean_filename(typed, "xlsx") == expected


@pytest.mark.parametrize("typed", ["", "   ", ".xlsx", "///"])
def test_clean_filename_rejects_empty_names(typed):
    with pytest.raises(ValueError):
        clean_filename(typed, "xlsx")


def test_copy_to_folder_on_computer(tmp_path):
    source = tmp_path / "draft.pdf"
    source.write_bytes(b"%PDF-report")
    folder = tmp_path / "Laporan Kos"
    folder.mkdir()
    saved = copy_to_folder(source, folder, "November.pdf")
    assert saved == folder / "November.pdf"
    assert saved.read_bytes() == b"%PDF-report"


def test_copy_to_missing_folder_fails_clearly(tmp_path):
    source = tmp_path / "draft.pdf"
    source.write_bytes(b"x")
    with pytest.raises(ValueError, match="Folder tidak ditemukan"):
        copy_to_folder(source, tmp_path / "hilang", "a.pdf")


# A fake Android: system save screen, content resolver, and output stream.


class Intent:
    ACTION_CREATE_DOCUMENT = "android.intent.action.CREATE_DOCUMENT"
    ACTION_VIEW = "android.intent.action.VIEW"
    CATEGORY_OPENABLE = "android.intent.category.OPENABLE"
    EXTRA_TITLE = "android.intent.extra.TITLE"
    FLAG_GRANT_READ_URI_PERMISSION = 1
    FLAG_ACTIVITY_NEW_TASK = 0x10000000

    def __init__(self, action):
        self.action, self.categories, self.extras, self.flags = action, [], {}, 0
        self.mime = self.data = None

    def addCategory(self, category):
        self.categories.append(category)

    def setType(self, mime):
        self.mime = mime

    def putExtra(self, key, value):
        self.extras[key] = value

    def setDataAndType(self, data, mime):
        self.data, self.mime = data, mime

    def addFlags(self, flags):
        self.flags |= flags


class Result:
    def __init__(self, uri):
        self.uri = uri

    def getData(self):
        return self.uri


class Stream:
    def __init__(self, fail=False):
        self.written, self.writes, self.closed, self.fail = bytearray(), 0, False, fail

    def write(self, chunk, offset, length):
        if self.fail:
            raise OSError("disk penuh")
        self.written.extend(chunk[offset : offset + length])
        self.writes += 1

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Cursor:
    def __init__(self, name):
        self.name, self.closed = name, False

    def moveToFirst(self):
        return True

    def getString(self, _index):
        return self.name

    def close(self):
        self.closed = True


class Resolver:
    def __init__(self, phone):
        self.phone = phone

    def openOutputStream(self, uri, mode):
        if mode == "wt" and not self.phone.supports_truncate:
            raise Exception("mode wt unsupported")
        self.phone.modes.append(mode)
        return self.phone.stream

    def query(self, uri, columns, *_):
        assert columns == ["_display_name"]
        self.phone.cursor = Cursor(self.phone.provider_name)
        return self.phone.cursor


class Phone:
    def __init__(self, provider_name="kossplit-2026-11-03 (1).xlsx", supports_truncate=True, stream=None):
        self.provider_name = provider_name
        self.supports_truncate = supports_truncate
        self.stream = stream or Stream()
        self.modes, self.started, self.cursor = [], [], None
        self.listeners, self.picker_broken = [], False
        phone = self

        class Activity:
            def startActivityForResult(self, intent, code):
                if phone.picker_broken:
                    raise Exception("No activity found")
                phone.started.append((intent, code))

            def startActivity(self, intent):
                phone.started.append((intent, None))

            def getContentResolver(self):
                return Resolver(phone)

        self.activity = Activity()

    def autoclass(self, name):
        if name == "android.content.Intent":
            return Intent
        if name == "org.kivy.android.PythonActivity":
            return type("PythonActivity", (), {"mActivity": self.activity})
        if name == "android.app.Activity":
            return type("Activity", (), {"RESULT_OK": RESULT_OK})
        raise AssertionError(name)

    # android.activity event dispatcher
    def bind(self, on_activity_result):
        self.listeners.append(on_activity_result)

    def unbind(self, on_activity_result):
        self.listeners.remove(on_activity_result)

    def finish_picker(self, result_code, uri="content://downloads/document/42", request=REQUEST_SAVE):
        for listener in list(self.listeners):
            listener(request, result_code, Result(uri) if uri else None)


@pytest.fixture
def outcome():
    return {}


def start_save(phone, outcome, data=b"PK\x03\x04 laporan", filename="kossplit-2026-11-03.xlsx"):
    saver = AndroidDocumentSaver(autoclass=phone.autoclass, activity_events=phone, post=lambda cb, *a: cb(*a))
    saver.save(
        data,
        filename,
        mime_type("xlsx"),
        on_saved=lambda name, uri: outcome.update(saved=(name, uri)),
        on_cancel=lambda: outcome.update(cancelled=True),
        on_error=lambda message: outcome.update(error=message),
    )
    return saver


def test_opens_android_save_screen_with_suggested_name(outcome):
    phone = Phone()
    start_save(phone, outcome)
    intent, code = phone.started[0]
    assert code == REQUEST_SAVE
    assert intent.action == Intent.ACTION_CREATE_DOCUMENT
    assert intent.categories == [Intent.CATEGORY_OPENABLE]
    assert intent.mime == mime_type("xlsx")
    assert intent.extras[Intent.EXTRA_TITLE] == "kossplit-2026-11-03.xlsx"


def test_writes_report_to_chosen_location_and_reports_provider_name(outcome):
    phone = Phone()
    data = bytes(range(256)) * ((CHUNK_SIZE * 3) // 256 + 7)  # several chunks
    start_save(phone, outcome, data=data)
    phone.finish_picker(RESULT_OK)
    assert bytes(phone.stream.written) == data
    assert phone.stream.writes > 1 and phone.stream.closed
    assert phone.modes == ["wt"]
    assert outcome["saved"] == ("kossplit-2026-11-03 (1).xlsx", "content://downloads/document/42")
    assert phone.cursor.closed
    assert phone.listeners == []


def test_cancelled_save_screen_writes_nothing(outcome):
    phone = Phone()
    start_save(phone, outcome)
    phone.finish_picker(RESULT_CANCELED, uri=None)
    assert outcome == {"cancelled": True}
    assert phone.stream.written == bytearray()
    assert phone.listeners == []


def test_ignores_results_meant_for_the_receipt_scanner(outcome):
    phone = Phone()
    start_save(phone, outcome)
    phone.finish_picker(RESULT_OK, request=4711)
    assert outcome == {}
    assert len(phone.listeners) == 1


def test_falls_back_when_provider_lacks_truncate_mode(outcome):
    phone = Phone(supports_truncate=False)
    start_save(phone, outcome)
    phone.finish_picker(RESULT_OK)
    assert phone.modes == ["w"]
    assert "saved" in outcome


def test_write_failure_is_reported_not_crashing(outcome):
    phone = Phone(stream=Stream(fail=True))
    start_save(phone, outcome)
    phone.finish_picker(RESULT_OK)
    assert outcome["error"].startswith("Laporan gagal disimpan")
    assert phone.stream.closed


def test_missing_save_screen_is_reported(outcome):
    phone = Phone()
    phone.picker_broken = True
    start_save(phone, outcome)
    assert outcome["error"].startswith("Pemilih lokasi tidak dapat dibuka")
    assert phone.listeners == []


def test_open_saved_report_grants_read_access(outcome):
    phone = Phone()
    saver = start_save(phone, outcome)
    assert saver.open("content://downloads/document/42", "application/pdf")
    intent, _ = phone.started[-1]
    assert intent.action == Intent.ACTION_VIEW
    assert intent.data == "content://downloads/document/42" and intent.mime == "application/pdf"
    assert intent.flags & Intent.FLAG_GRANT_READ_URI_PERMISSION


@pytest.mark.parametrize(("extension", "signature"), [("xlsx", b"PK"), ("pdf", b"%PDF")])
def test_real_reports_arrive_intact_at_chosen_location(tmp_path, outcome, extension, signature):
    database = Database(tmp_path / "kos.db")
    ayu = database.add_member("Ayu", is_owner=True)
    database.add_transaction(ayu, "expense", "Makan & Minum", "Nasi goreng", 48_000)
    draft = tmp_path / report_filename(extension)
    exporter = export_excel if extension == "xlsx" else export_pdf
    exporter(draft, database.recent_bills(1000), database.all_transactions(5000))
    data = draft.read_bytes()

    phone = Phone(provider_name=draft.name)
    start_save(phone, outcome, data=data, filename=draft.name)
    phone.finish_picker(RESULT_OK)
    assert bytes(phone.stream.written) == data
    assert data.startswith(signature)
    assert outcome["saved"][0] == draft.name
