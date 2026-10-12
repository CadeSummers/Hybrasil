# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The write path into the catalog workbook, exercised without a network."""

import json

import pytest

from hybrasil.data import google_sheets as gs


# ---------------------------------------------------------------------------
# A stand-in for the spreadsheets() handle _sheets_api() returns.
# ---------------------------------------------------------------------------

class _Call:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _Values:
    def __init__(self, get_payload, update_payload, log):
        self._get = get_payload
        self._update = update_payload
        self.log = log

    def batchGet(self, **kwargs):
        self.log.append(("batchGet", kwargs))
        return _Call(self._get)

    def batchUpdate(self, **kwargs):
        self.log.append(("batchUpdate", kwargs))
        return _Call(self._update)


class _Api:
    def __init__(self, get_payload, update_payload, log):
        self._values = _Values(get_payload, update_payload, log)

    def values(self):
        return self._values


@pytest.fixture
def api(monkeypatch):
    """Install a fake Sheets handle; the returned log records every call."""
    log = []
    state = {"get": {"valueRanges": []}, "update": {"totalUpdatedCells": 0}}

    def install(get_payload=None, update_payload=None):
        if get_payload is not None:
            state["get"] = get_payload
        if update_payload is not None:
            state["update"] = update_payload

    monkeypatch.setattr(gs, "_sheets_api",
                        lambda: _Api(state["get"], state["update"], log))
    install.log = log
    return install


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("HYBRASIL_CACHE_DIR", str(tmp_path))
    return tmp_path


SHEET = "test-sheet-id"
CELL = "'Systems within 100 ly'!J4"


class TestScope:
    def test_the_scope_permits_writing(self):
        """A revert to spreadsheets.readonly would break every write silently."""
        assert gs.SCOPES == ["https://www.googleapis.com/auth/spreadsheets"]


class TestSpreadsheetId:
    """The workbook is private: its ID comes from the environment, never the source."""

    @pytest.fixture(autouse=True)
    def empty_config(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HYBRASIL_SHEET_ID", raising=False)
        monkeypatch.setenv("HYBRASIL_CONFIG_DIR", str(tmp_path))
        return tmp_path

    def test_unconfigured_is_an_error_not_a_default(self):
        with pytest.raises(RuntimeError, match="No spreadsheet ID"):
            gs.resolve_spreadsheet_id()

    def test_read_from_the_config_file(self, empty_config):
        (empty_config / gs.SHEET_ID_FILE).write_text("from-file\n", encoding="utf-8")
        assert gs.resolve_spreadsheet_id() == "from-file"

    def test_environment_beats_the_file(self, empty_config, monkeypatch):
        (empty_config / gs.SHEET_ID_FILE).write_text("from-file", encoding="utf-8")
        monkeypatch.setenv("HYBRASIL_SHEET_ID", "from-env")
        assert gs.resolve_spreadsheet_id() == "from-env"

    def test_explicit_beats_everything_and_urls_are_trimmed(self, monkeypatch):
        monkeypatch.setenv("HYBRASIL_SHEET_ID", "from-env")
        url = "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"
        assert gs.resolve_spreadsheet_id(url) == "abc123"


class TestAsGrid:
    def test_scalar_becomes_one_cell(self):
        assert gs._as_grid("Binary Brown Dwarfs") == [["Binary Brown Dwarfs"]]

    def test_row_becomes_one_row(self):
        assert gs._as_grid(["a", "b"]) == [["a", "b"]]

    def test_grid_is_left_alone(self):
        assert gs._as_grid([["a"], ["b"]]) == [["a"], ["b"]]


class TestReadCells:
    def test_values_come_back_keyed_by_range(self, api):
        api({"valueRanges": [{"values": [["binary brown dwarfs"]]}]})
        assert gs.read_cells(SHEET, [CELL]) == {CELL: [["binary brown dwarfs"]]}

    def test_an_empty_range_maps_to_an_empty_list(self, api):
        api({"valueRanges": [{}]})
        assert gs.read_cells(SHEET, [CELL]) == {CELL: []}

    def test_no_ranges_makes_no_call(self, api):
        assert gs.read_cells(SHEET, []) == {}
        assert api.log == []


class TestUpdateCells:
    def test_nothing_to_write_makes_no_call(self, api):
        assert gs.update_cells(SHEET, {}) == 0
        assert api.log == []

    def test_a_guarded_write_sends_the_value(self, api):
        api({"valueRanges": [{"values": [["binary brown dwarfs"]]}]},
            {"totalUpdatedCells": 1})
        written = gs.update_cells(
            SHEET,
            {CELL: "Binary Brown Dwarfs"},
            expect={CELL: "binary brown dwarfs"},
        )
        assert written == 1
        kinds = [kind for kind, _ in api.log]
        assert kinds == ["batchGet", "batchUpdate"]
        body = api.log[1][1]["body"]
        assert body["valueInputOption"] == "RAW"
        assert body["data"] == [{"range": CELL, "values": [["Binary Brown Dwarfs"]]}]

    def test_a_mismatch_aborts_before_writing(self, api):
        api({"valueRanges": [{"values": [["something else"]]}]})
        with pytest.raises(gs.CellMismatch) as excinfo:
            gs.update_cells(SHEET, {CELL: "Binary Brown Dwarfs"},
                            expect={CELL: "binary brown dwarfs"})
        assert "something else" in str(excinfo.value)
        assert [kind for kind, _ in api.log] == ["batchGet"]

    def test_an_empty_cell_counts_as_a_mismatch(self, api):
        api({"valueRanges": [{}]})
        with pytest.raises(gs.CellMismatch):
            gs.update_cells(SHEET, {CELL: "x"}, expect={CELL: "binary brown dwarfs"})

    def test_user_entered_can_be_requested(self, api):
        api({"valueRanges": []}, {"totalUpdatedCells": 1})
        gs.update_cells(SHEET, {CELL: "=SUM(A1:A2)"}, value_input="USER_ENTERED")
        assert api.log[0][1]["body"]["valueInputOption"] == "USER_ENTERED"

    def test_writing_drops_the_stale_cache(self, api, isolated_cache):
        path = gs.cache_path(SHEET)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"spreadsheet_id": SHEET}), encoding="utf-8")
        api({"valueRanges": []}, {"totalUpdatedCells": 1})
        gs.update_cells(SHEET, {CELL: "Binary Brown Dwarfs"})
        assert not path.exists()


class TestInvalidateCache:
    def test_removes_an_existing_file(self, isolated_cache):
        path = gs.cache_path(SHEET)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        assert gs.invalidate_cache(SHEET) is True
        assert not path.exists()

    def test_missing_file_is_not_an_error(self, isolated_cache):
        assert gs.invalidate_cache(SHEET) is False
