import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin-data"))
    monkeypatch.delenv("OOSTERVELDE_DATA", raising=False)
    monkeypatch.setattr(server, "pick_folder", lambda: pytest.fail("picker opened"))


def test_empty_folder_gets_sample(tmp_path):
    r = server.setup(str(tmp_path / "new"))
    assert r["folder"] == str(tmp_path / "new")
    assert len(list((tmp_path / "new" / "invoices").glob("*.txt"))) == 40
    assert server.has_structure(tmp_path / "new")


def test_existing_structure_is_used_as_is(tmp_path):
    server.setup(str(tmp_path / "a"))
    (tmp_path / "a" / "invoices" / "extra.txt").write_text("mine")
    r = server.setup(str(tmp_path / "a"))
    assert r["action"] == "used the existing folder"
    assert (tmp_path / "a" / "invoices" / "extra.txt").read_text() == "mine"


def test_unrelated_folder_gets_subfolder(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "taxes.pdf").write_text("x")
    r = server.setup(str(tmp_path / "docs"))
    assert r["folder"] == str(tmp_path / "docs" / "Oostervelde")
    assert server.has_structure(tmp_path / "docs" / "Oostervelde")
    assert (tmp_path / "docs" / "taxes.pdf").read_text() == "x"


def test_saved_config_is_reused_without_picker(tmp_path):
    server.setup(str(tmp_path / "a"))
    r = server.setup()
    assert r["status"] == "ready" and r["folder"] == str(tmp_path / "a")
    assert server.base(None) == (tmp_path / "a").resolve()


def test_picker_used_then_cancel_asks_in_chat(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "pick_folder", lambda: str(tmp_path / "picked"))
    assert server.setup()["folder"] == str(tmp_path / "picked")
    monkeypatch.setattr(server, "saved_folder", lambda: None)
    monkeypatch.setattr(server, "pick_folder", lambda: "")
    assert server.setup()["status"] == "ask_in_chat"


def test_no_folder_saved_is_an_error():
    with pytest.raises(ValueError, match="setup"):
        server.base(None)
