"""Sanne's workflow across months: January = the real 40 invoices, February = a few hand-written invoices."""
import csv
import http.client
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dashboard  # noqa: E402
import rules  # noqa: E402
import server  # noqa: E402

JAN, FEB = "2026-01", "2026-02"

# Bosman layout (copied from b-B-26-0131.txt), with the credit reference line of the Hoekstra credit note.
BOSMAN_CREDIT = """DAKWERKEN BOSMAN & ZN.   Havenstraat 22, 6827 BL Arnhem
KvK 00000003   IBAN NL00 TEST 0000 0000 03

FACTUUR  nr. {nr}   datum 2026-02-10
Betreft creditering van factuur B-26-0131
Opdrachtgever: Woonkring Oostervelde (werkorder WO-26-1015)
Locatie: Daalhuizerweg 66, Velp
Uitvoeringsdatum: 2026-01-21

 1. Creditering meerwerk boven GA-0419       |   -1 post  | a    {ex:>6} |    -{ex}

                                   netto    -{ex}
  BTW 21% over -{ex}: -{vat}
                                   totaal   -{inc}
"""


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("OOSTERVELDE_NO_DASHBOARD", "1")
    for name in ("price-agreement-2025.csv", "work-orders-export.csv", "contract-excerpt.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "invoices", tmp_path / "invoices" / JAN)
    (tmp_path / "invoices" / FEB).mkdir()
    server.check_all(month=JAN, folder=str(tmp_path))
    return tmp_path.resolve()


def feb(data, name, text):
    (data / "invoices" / FEB / name).write_text(text, encoding="utf-8")


def bosman_credit(data, nr, ex, vat, inc):
    feb(data, f"b-{nr}.txt", BOSMAN_CREDIT.format(nr=nr, ex=ex, vat=vat, inc=inc))


def corrected_0061(data):
    text = (ROOT / "invoices" / "h-2026-0061.txt").read_text(encoding="utf-8")
    text = (text.replace("Factuurnummer: 2026-0061", "Factuurnummer: 2026-0071")
            .replace("Factuurdatum:  30-01-2026", "Factuurdatum:  05-02-2026")
            .replace("BTW 9% over 418,99: 37,71", "BTW 21% over 418,99: 87,99")
            .replace("TOTAAL TE BETALEN: EUR 456,70", "TOTAAL TE BETALEN: EUR 506,98"))
    feb(data, "h-2026-0071.txt", text)


def result(data, month, invoice):
    return next(r for r in server.run_checks(data, month)[1] if r.invoice == invoice)


def meta(data, month):
    return server.refresh(data, month)[2]


def rows(data):
    p = data / "decisions.csv"
    return list(csv.DictReader(open(p, encoding="utf-8", newline=""))) if p.exists() else []


def send_letter(data, invoice, when=None):
    server.record_decision(invoice, "letter_ok", folder=str(data))
    return server.record_decision(invoice, "sent", sent_date=when, folder=str(data))


# ---------------------------------------------------------------- (a) to (d): cross-month matching

def test_a_credit_note_resolves_dispute(data):
    out = server.record_decision("b-B-26-0131", "letter_ok", folder=str(data))
    assert out["status"] == "letter_ready" and out["letter_ready"].endswith("letters/b-B-26-0131.txt")
    assert server.record_decision("b-B-26-0131", "sent", folder=str(data))["status"] == "waiting"
    bosman_credit(data, "B-26-C011", "240,00", "50,40", "290,40")
    s = server.check_all(month=FEB, folder=str(data))
    cn = result(data, FEB, "b-B-26-C011")
    assert cn.verdict == "approve" and not any(f.hold for f in cn.findings)
    assert cn.linked_invoice == "b-B-26-0131" and cn.link["match"] == "full"
    assert cn.link["proposed_status"] == "credit received, matches"
    assert any("settles the dispute on invoice B-26-0131" in x["plain"] for x in cn.readings)
    assert s["needs_attention"] == [{"invoice": "b-B-26-0131", "month": JAN, "update": "credit_received",
                                     "linked_invoice": "b-B-26-C011", "arrived": FEB}]
    carried = {c["id"]: c for c in meta(data, FEB)["carried"]}
    assert carried["b-B-26-0131"]["status"] == "waiting" and "resolved" in carried["b-B-26-0131"]["actions"]
    assert meta(data, JAN)["invoices"]["b-B-26-0131"]["update"]["update"] == "credit_received"  # either month
    done = server.record_decision("b-B-26-0131", "resolved", kind="credit_note", reason="Credit note C011",
                                  folder=str(data))
    assert done["status"] == "resolved" and done["recorded"]["linked_invoice"] == "b-B-26-C011"
    assert done["recorded"]["overrule"] == "no"
    cn = result(data, FEB, "b-B-26-C011")  # still matched after the original is resolved
    assert cn.verdict == "approve" and cn.link["match"] == "full"
    m = meta(data, FEB)
    assert m["needs_attention"] == [] and {c["id"]: c for c in m["carried"]}["b-B-26-0131"]["status"] == "resolved"


def test_b_smaller_credit_leaves_rest_open(data):
    send_letter(data, "b-B-26-0131")
    bosman_credit(data, "B-26-C012", "100,00", "21,00", "121,00")
    cn = result(data, FEB, "b-B-26-C012")
    assert cn.verdict == "approve" and cn.link["match"] == "partial"
    assert str(cn.link["remaining_incl_vat"]) == "169.40"
    m = meta(data, FEB)
    c = {x["id"]: x for x in m["carried"]}["b-B-26-0131"]
    assert c["status"] == "waiting" and c["update"]["update"] == "credit_partial"


def test_larger_credit_is_high_risk_and_not_resolved(data):
    send_letter(data, "b-B-26-0131")
    bosman_credit(data, "B-26-C013", "300,00", "63,00", "363,00")
    cn = result(data, FEB, "b-B-26-C013")
    assert cn.risk == "high" and cn.link["match"] == "over" and cn.link["proposed_status"] is None
    assert server.invoice_states(rows(data))["b-B-26-0131"]["status"] == "waiting"


def test_credit_without_history_match_still_held(data):
    bosman_credit(data, "B-26-C014", "240,00", "50,40", "290,40")  # B-26-0131 was never disputed
    cn = result(data, FEB, "b-B-26-C014")
    assert cn.verdict == "hold" and cn.findings[0].rule == "R14"


def test_c_corrected_invoice_is_not_a_duplicate(data):
    send_letter(data, "h-2026-0061")
    corrected_0061(data)
    r = result(data, FEB, "h-2026-0071")
    assert r.verdict == "approve" and not any(f.rule == "R13" for f in r.findings)
    assert r.linked_invoice == "h-2026-0061" and r.link["kind"] == "corrected_invoice"
    assert server.check_all(month=FEB, folder=str(data))["needs_attention"][0]["update"] == "correction_received"


def test_corrected_invoice_without_open_dispute_is_a_duplicate(data):
    server.record_decision("h-2026-0061", "pay", reason="Accepted the low VAT", folder=str(data))
    corrected_0061(data)
    assert result(data, FEB, "h-2026-0071").findings[0].rule == "R13"


def test_d_duplicate_resent_in_february_is_caught(data):
    server.record_decision("j-F26-0001", "pay", folder=str(data))
    shutil.copy(ROOT / "invoices" / "j-F26-0019.txt", data / "invoices" / FEB / "j-F26-0019.txt")
    r = result(data, FEB, "j-F26-0019")
    assert r.verdict == "dispute" and [f.rule for f in r.findings] == ["R13"]
    assert "already invoiced on j-F26-0001" in r.findings[0].issue


# ---------------------------------------------------------------- (e) to (g): lifecycle rules

def test_e_sent_before_letter_ok_refused(data):
    with pytest.raises(ValueError, match="letter is ready"):
        server.record_decision("b-B-26-0131", "sent", folder=str(data))
    assert rows(data) == []


def test_g_days_waiting(data):
    when = (date.today() - timedelta(days=5)).isoformat()
    out = send_letter(data, "b-B-26-0131", when)
    assert out["days_waiting"] == 5 and out["recorded"]["sent_date"] == when
    assert meta(data, JAN)["invoices"]["b-B-26-0131"]["days_waiting"] == 5
    assert {c["id"]: c for c in meta(data, FEB)["carried"]}["b-B-26-0131"]["days_waiting"] == 5
    server.record_decision("b-B-26-0089", "letter_ok", folder=str(data))
    with pytest.raises(ValueError, match="future"):
        server.record_decision("b-B-26-0089", "sent", sent_date=(date.today() + timedelta(days=1)).isoformat(),
                               folder=str(data))


def test_undo_steps_back_one_state(data):
    send_letter(data, "b-B-26-0131")
    out = server.record_decision("b-B-26-0131", "undo", folder=str(data))
    assert out["status"] == "letter_ready" and len(rows(data)) == 3
    assert server.record_decision("b-B-26-0131", "undo", folder=str(data))["status"] == "open"


def test_hold_confirmed_and_not_ours(data):
    assert result(data, JAN, "w-DW26-013").verdict == "hold"
    assert server.record_decision("w-DW26-013", "hold", folder=str(data))["status"] == "on_hold"
    out = server.record_decision("w-DW26-013", "confirmed", reason="Housing officer confirmed", folder=str(data))
    r = result(data, JAN, "w-DW26-013")
    assert out["status"] == "open" and r.verdict != "hold" and not any(f.rule == "R15" for f in r.findings)
    with pytest.raises(ValueError, match="unknown work order"):
        server.record_decision("w-DW26-013", "confirmed", folder=str(data))
    with pytest.raises(ValueError, match="reason"):
        server.record_decision("b-B-26-0089", "not_ours", folder=str(data))
    out = server.record_decision("b-B-26-0089", "not_ours", reason="Not our job", folder=str(data))
    assert out["status"] == "disputed_full" and out["recorded"]["amount_incl_vat"] == "2098.87"
    text = (data / out["letter_ready"]).read_text(encoding="utf-8")
    assert '"' + rules.REFS["4.9"][2] + '"' in text and "EUR 2.098,87 incl. btw" in text


def test_old_decisions_file_still_loads_and_is_extended(data):
    old = ",".join(server.OLD_COLUMNS) + "\n" + \
        "2026-02-01T10:00:00,b-B-26-0131,WO-26-1015,Bosman,dispute,dispute,240.00,290.40,,no,R9,640.00\n"
    (data / "decisions.csv").write_text(old, encoding="utf-8")
    assert server.invoice_states(rows(data))["b-B-26-0131"]["status"] == "letter_ready"
    assert server.record_decision("b-B-26-0131", "sent", folder=str(data))["status"] == "waiting"
    text = (data / "decisions.csv").read_text(encoding="utf-8")
    assert text.splitlines()[0] == ",".join(server.COLUMNS) and old.splitlines()[1] in text


# ---------------------------------------------------------------- small findings, repeats, settings

def test_let_go_and_repeat(data):
    with pytest.raises(ValueError, match="small"):
        server.record_decision("b-B-26-0131", "let_go", folder=str(data))
    assert all(f.small for f in result(data, JAN, "h-2026-0038").findings)
    for n in range(3):  # three earlier let-gos for Hoekstra on R1
        server.append_row(data, {**dict.fromkeys(server.COLUMNS, ""), "timestamp": "2025-12-01T10:00:00",
                                 "invoice": f"h-2025-09{n}", "contractor": "Hoekstra", "decision": "let_go",
                                 "status": "to_pay", "overrule": "no", "rules": "R1", "let_go": "R1"})
    r = result(data, JAN, "h-2026-0038")
    assert all(f.repeat and not f.small and f.repeat_count == 3 for f in r.findings)
    assert [str(f.disputed_excl_vat) for f in r.findings] == ["18.50", "5.61"]  # amounts unchanged
    m = meta(data, JAN)["invoices"]["h-2026-0038"]
    assert m["repeat"] and not m["small"] and m["findings"][0]["repeat_count"] == 3
    assert m["findings"][0]["plain"].startswith("Hoekstra charged this 3 times before; you let it go each time.")
    with pytest.raises(ValueError, match="reason"):
        server.record_decision("h-2026-0038", "let_go", folder=str(data))
    out = server.record_decision("h-2026-0038", "let_go", reason="Rounding, agreed", folder=str(data))
    assert out["status"] == "to_pay" and out["recorded"]["overrule"] == "yes" and out["recorded"]["let_go"] == "R1 R1"
    other = server.record_decision("b-B-26-0144", "let_go", folder=str(data))  # Bosman R1: small, no repeat
    assert other["recorded"]["overrule"] == "no" and other["status"] == "to_pay"


def test_threshold_relabels_but_never_changes_amounts(data):
    before = result(data, JAN, "b-B-26-0089")
    assert not before.findings[0].small
    server.save_settings(data, {"small_threshold_excl_vat": "50.00"})
    after = result(data, JAN, "b-B-26-0089")
    assert after.findings[0].small and after.total_disputed_incl_vat == before.total_disputed_incl_vat
    assert not any(f.small for f in result(data, JAN, "h-2026-0061").findings)  # VAT-rate findings never small
    assert rules.is_small(after.findings[0]) is False  # rules default stays 25.00


def test_letters_use_settings(data):
    server.save_settings(data, {"signer": "Sanne de Vries", "closing": "Hoogachtend,", "num": "en"})
    out = server.record_decision("b-B-26-0131", "letter_ok", folder=str(data))
    text = (data / out["letter_ready"]).read_text(encoding="utf-8")
    assert text.endswith("Hoogachtend,\n\nSanne de Vries\nWoonkring Oostervelde, crediteurenadministratie\n")
    assert "EUR 240.00 excl. btw" in text


# ---------------------------------------------------------------- plain language

def test_plain_readings_have_no_ids(data):
    m = meta(data, JAN)
    ids = re.compile(r"\b[RQ]\d+\b|\b[HWBJ]\d{2}\b")
    seen = 0
    for inv in m["invoices"].values():
        for f in inv["findings"]:
            assert f["plain"] and not ids.search(f["plain"]), f["plain"]
            seen += 1
        for x in inv["readings"]:
            assert x["plain"] and not ids.search(x["plain"]), x["plain"]
        assert ".;" not in inv["reading"]
    assert seen > 20
    h49 = m["invoices"]["h-2026-0049"]
    assert "settled by the credit note" in h49["reading"]
    assert {r["label"] for x in h49["readings"] for r in x["refs"]} == {"Art. 4.8"}


# ---------------------------------------------------------------- dashboard: (f), (h), settings

def call(d, method, path, body=None, token=True):
    h = {"Host": f"127.0.0.1:{d.port}"}
    if token:
        h["X-Token"] = d.token
    c = http.client.HTTPConnection("127.0.0.1", d.port, timeout=30)
    c.request(method, path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    return r.status, raw


def post(d, path, body, **kw):
    status, raw = call(d, "POST", path, body, **kw)
    return status, json.loads(raw)


@pytest.fixture
def dash(data):
    made = []

    def start(month=JAN):
        x = dashboard.Dashboard(server, ports=(0,))
        x.serve(data, month)
        made.append(x)
        return x
    yield start
    for x in made:
        x.stop()


def test_f_resolved_needs_kind_and_reason(data, dash):
    d = dash()
    for b in ({"decision": "letter_ok"}, {"decision": "sent"}):
        assert post(d, "/api/decision", {"invoice": "b-B-26-0131", "month": JAN, **b})[0] == 200
    n = len(rows(data))
    for bad in ({}, {"kind": "credit_note"}, {"reason": "ok"}, {"kind": "paid", "reason": "ok"}):
        assert post(d, "/api/decision", {"invoice": "b-B-26-0131", "month": JAN, "decision": "resolved", **bad})[0] == 400
    assert post(d, "/api/decision", {"invoice": "b-B-26-0089", "month": JAN, "decision": "sent"})[0] == 400  # (e)
    assert len(rows(data)) == n


def test_h_lifecycle_survives_restart(data, dash):
    d = dash()
    for b in ({"decision": "letter_ok"}, {"decision": "sent", "date": "2026-02-02"}):
        assert post(d, "/api/decision", {"invoice": "b-B-26-0131", "month": JAN, **b})[0] == 200
    bosman_credit(data, "B-26-C011", "240,00", "50,40", "290,40")
    assert call(d, "GET", f"/?month={FEB}")[0] == 200
    status, out = post(d, "/api/decision", {"invoice": "b-B-26-0131", "month": FEB, "decision": "resolved",
                                            "kind": "credit_note", "reason": "Credit C011 matches"})
    assert status == 200 and out["row"]["status"] == "resolved"
    res = post(d, "/api/decision", {"invoice": "b-B-26-C011", "month": FEB, "decision": "pay"})
    assert res[0] == 200, res[1]
    d.stop()
    d2 = dash(FEB)
    assert call(d2, "GET", f"/?month={FEB}")[0] == 200
    st = server.invoice_states(rows(data))
    assert st["b-B-26-0131"]["status"] == "resolved" and st["b-B-26-0131"]["sent_date"] == "2026-02-02"
    assert st["b-B-26-0131"]["resolved_kind"] == "credit_note" and st["b-B-26-C011"]["status"] == "to_pay"
    m = meta(data, FEB)
    assert m["invoices"]["b-B-26-C011"]["status"] == "to_pay" and m["status_counts"]["to_pay"] == 1
    assert {c["id"]: c for c in m["carried"]}["b-B-26-0131"]["status"] == "resolved"
    assert post(d2, "/api/decision", {"invoice": "b-B-26-0131", "month": FEB, "decision": "undo"})[1]["row"]["status"] == "waiting"


def test_settings_endpoint(data, dash):
    d = dash()
    bad = [{"small_threshold_excl_vat": "1000.01"}, {"small_threshold_excl_vat": "-1"},
           {"small_threshold_excl_vat": "1.234"}, {"small_threshold_excl_vat": "abc"},
           {"small_threshold_excl_vat": True}, {"signer": "x" * 201}, {"greeting": ""}, {"num": "fr"},
           {"repeat_threshold": 0}]
    for b in bad:
        assert post(d, "/api/settings", b)[0] == 400, b
    assert not (data / "settings.json").exists()
    assert call(d, "POST", "/api/settings", {"signer": "S"}, token=False)[0] == 403
    status, out = post(d, "/api/settings", {"small_threshold_excl_vat": "40", "signer": "Sanne", "month": JAN})
    assert status == 200 and out["settings"]["small_threshold_excl_vat"] == "40.00"
    saved = json.loads((data / "settings.json").read_text(encoding="utf-8"))
    assert saved["signer"] == "Sanne" and saved["repeat_threshold"] == 3
    assert result(data, JAN, "b-B-26-0089").findings[0].small


def test_corrected_invoice_shows_previous_version(data):
    import report
    send_letter(data, "h-2026-0061")
    corrected_0061(data)
    page = server.refresh(data, FEB)
    html = report.render(*page)
    new = {x["id"]: x for x in report.build_data(*page)["invoices"]}["h-2026-0071"]
    # the replacement links to its original through data, not a banner
    assert new["link"]["invoice"] == "h-2026-0061" and new["previous"]["month"] == JAN
    assert "'Replaces '" not in html  # no banner on the replacement; the previous version section carries it
    # previous version: raw text, findings in plain words, amounts
    prev = new["previous"]
    assert prev["raw"] == (ROOT / "invoices" / "h-2026-0061.txt").read_text(encoding="utf-8")
    assert prev["findings"] and any("VAT" in f["plain"] for f in prev["findings"])
    assert prev["total"] == "456.70" and new["total"] == "506.98"
    assert "Previous version" in html
    # banner on the original: "Replaced by <new> (<month>)"
    old = report.build_data(*server.refresh(data, JAN))["invoices"]
    upd = {x["id"]: x for x in old}["h-2026-0061"]["update"]
    assert upd["update"] == "correction_received" and upd["linked_invoice"] == "h-2026-0071" and upd["month"] == FEB
    assert "'Replaced by '+l+' ('+m+')'" in html
