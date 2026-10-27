import csv
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import server  # noqa: E402


@pytest.fixture
def data(tmp_path):
    for name in ("price-agreement-2025.csv", "work-orders-export.csv", "contract-excerpt.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "invoices", tmp_path / "invoices")
    return str(tmp_path)


def first(summary, verdict, folder):
    review = (Path(folder) / summary["review_list"]).read_text(encoding="utf-8")
    inv = next(r for r in server.list_invoices(folder=folder)["invoices"]
               if server.check_invoice(r["invoice"], folder=folder)["verdict"] == verdict)["invoice"]
    return review, inv


def run_dir(data, s):
    return Path(data) / "output" / s["run"]


def test_check_all_writes_review_list_and_letters(data):
    s = server.check_all(folder=data)
    review, _ = first(s, "dispute", data)
    assert review.startswith("# Review list")
    assert review.index("## High risk") < review.index("## Low risk")
    assert "English translation of the letter" in review and "letters/" in review
    letters = list((run_dir(data, s) / "letters").glob("*.CONCEPT.txt"))
    assert len(letters) == s["letters"] == s["verdicts"]["dispute"] > 0
    text = letters[0].read_text(encoding="utf-8")
    assert text.startswith("Aan: ") and "CONCEPT" not in text and "DRAFT" not in text
    assert text.rstrip().endswith("Met vriendelijke groet,\n\nWoonkring Oostervelde, crediteurenadministratie")
    assert chr(0x2014) not in review + text


def page_data(html):
    """The JSON data block of review.html."""
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
    return json.loads(m.group(1))


def test_letter_parts_roundtrip_and_page_data(data):
    s = server.check_all(folder=data)
    html = (run_dir(data, s) / "review.html").read_text(encoding="utf-8")
    page = page_data(html)
    withletter = [x for x in page["invoices"] if x["letter"]]
    assert withletter
    for x in withletter:
        text = (run_dir(data, s) / "letters" / f"{x['id']}.CONCEPT.txt").read_text(encoding="utf-8")
        d = page["defaults"]
        parts = [x["letter"]["head"], d["greeting"], x["letter"]["body"], d["closing"], d["dept"] + "\n"]
        assert "\n\n".join(parts) == text
    assert chr(0x2014) not in html


def test_review_html_exists_and_escapes(data):
    inv = Path(data) / "invoices" / "b-B-26-0131.txt"
    inv.write_text(inv.read_text(encoding="utf-8") + "\n<script>alert(1)</script>\n", encoding="utf-8")
    s = server.check_all(folder=data)
    html = (run_dir(data, s) / "review.html").read_text(encoding="utf-8")
    assert "\\u003cscript>alert(1)\\u003c/script>" in html  # in the JSON data block, "<" escaped
    assert "<script>alert(1)" not in html
    assert html.count("<script") == 2 and html.count("</script>") == 2  # data block + page script only
    assert "http://" not in html.replace("http://www.w3.org/2000/svg", "") and "https://" not in html


def test_letters_have_no_rule_ids_and_use_decimal_commas(data):
    s = server.check_all(folder=data)
    paths = list((run_dir(data, s) / "letters").glob("*.txt"))
    assert paths
    for p in paths:
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"\b[RQ]\d", text), p.name
        assert not re.search(r"EUR \d[\d.]*\.\d{2}\b", text), p.name
    assert any(re.search(r"EUR \d{1,3}(\.\d{3})*,\d{2}\b", p.read_text(encoding="utf-8")) for p in paths)


def test_letter_quotes_are_verbatim(data):
    s = server.check_all(folder=data)
    sources = {p.stem: re.sub(r"\s+", " ", p.read_text(encoding="utf-8")) for p in (Path(data) / "invoices").glob("*.txt")}
    contract = re.sub(r"\s+", " ", (Path(data) / "contract-excerpt.md").read_text(encoding="utf-8"))
    for p in (run_dir(data, s) / "letters").glob("*.txt"):
        for q in re.findall(r'"([^"]+)"', p.read_text(encoding="utf-8")):
            q = re.sub(r"\s+", " ", q)
            assert q in sources[p.name.split(".")[0]] or q in contract, (p.name, q)


def test_record_decision(data):
    s = server.check_all(folder=data)
    _, inv = first(s, "dispute", data)
    letters = run_dir(data, s) / "letters"
    assert (letters / f"{inv}.CONCEPT.txt").exists()
    with pytest.raises(ValueError, match="reason"):
        server.record_decision(inv, "approve", folder=data)
    out = server.record_decision(inv, "dispute", folder=data)
    assert out["recorded"]["overrule"] == "no"
    rows = list(csv.DictReader(open(Path(data) / "decisions.csv", encoding="utf-8", newline="")))
    assert len(rows) == 1 and rows[0]["invoice"] == inv and rows[0]["decision"] == "letter_ok"
    assert out["letter_ready"] == f"output/{s['run']}/letters/{inv}.txt"
    assert (letters / f"{inv}.txt").exists() and not (letters / f"{inv}.CONCEPT.txt").exists()
    html = (run_dir(data, s) / "review.html").read_text(encoding="utf-8")
    rows = {x["id"]: x for x in page_data(html)["invoices"]}  # her call shown, others still open
    assert rows[inv]["decision"]["d"] == "letter_ok" and any(x["decision"] is None for x in rows.values())
    over = server.record_decision(inv, "approve", reason="Approval sent by phone", folder=data)
    assert over["recorded"]["overrule"] == "yes" and all(n == 1 for n in over["overrule_counts"].values())
    assert over["letter_ready"] is None and not (letters / f"{inv}.txt").exists()
    page = page_data((run_dir(data, s) / "review.html").read_text(encoding="utf-8"))
    assert any((x["decision"] or {}).get("reason") == "Approval sent by phone" for x in page["invoices"])


def test_changed_amount_regenerates_letter(data):
    s = server.check_all(folder=data)
    _, inv = first(s, "dispute", data)
    out = server.record_decision(inv, "dispute", reason="Sanne: partial", amount_excl_vat="45.00", folder=data)
    assert "EUR 45,00 excl. btw" in (Path(data) / out["letter_ready"]).read_text(encoding="utf-8")


def test_month_subfolder(data):
    sub = Path(data) / "invoices" / "2026-02"
    sub.mkdir()
    (Path(data) / "invoices" / "h-2026-0031.txt").rename(sub / "h-2026-0031.txt")
    feb = server.list_invoices(month="2026-02", folder=data)["invoices"]
    assert [r["invoice"] for r in feb] == ["h-2026-0031"]
    assert server.check_invoice("h-2026-0031", folder=data)["invoice"] == "h-2026-0031"


def test_path_outside_folder_refused(data):
    for bad in ("../README.md", "..\\..\\secret", str(ROOT / "README.md")):
        with pytest.raises(ValueError):
            server.read_invoice(bad, folder=data)


def test_lookups(data):
    assert server.get_price("H02", "2026-01-06", folder=data)["applicable_price"] == "60.37"
    assert server.get_price("H02", "31-12-2025", folder=data)["price_year"] == "2025"
    assert server.get_work_order("WO-26-1001", folder=data)["type"] == "regulier"
    rule = server.get_rule("4.3", folder=data)
    assert rule["articles"][0]["dutch"].startswith("**4.3 Voorrijkosten")
    assert "name: invoice-check" in server.monthly_check()


def test_record_decision_custom_amount_applies_line_vat(data):
    # j-F26-0016 bills a single 21% rate: 100.01 excl -> 21.0021 VAT -> 121.01 incl
    out = server.record_decision("j-F26-0016", "dispute", reason="Partial", amount_excl_vat="100.01", folder=data)
    assert out["recorded"]["amount_incl_vat"] == "121.01"


@pytest.fixture(autouse=True)
def no_dashboard(monkeypatch):
    monkeypatch.setenv("OOSTERVELDE_NO_DASHBOARD", "1")
