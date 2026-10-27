import csv
import http.client
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dashboard  # noqa: E402
import server  # noqa: E402


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("OOSTERVELDE_NO_DASHBOARD", "1")
    for name in ("price-agreement-2025.csv", "work-orders-export.csv", "contract-excerpt.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "invoices", tmp_path / "invoices")
    server.check_all(folder=str(tmp_path))
    return tmp_path.resolve()


@pytest.fixture
def dash(data):
    made = []

    def start(ports=(0,)):
        x = dashboard.Dashboard(server, ports=ports)
        x.serve(data)
        made.append(x)
        return x
    yield start
    for x in made:
        x.stop()


def call(d, method, path, body=None, token=True, headers=None):
    h = {"Host": f"127.0.0.1:{d.port}"}
    if token:
        h["X-Token"] = d.token
    h.update(headers or {})
    c = http.client.HTTPConnection("127.0.0.1", d.port, timeout=10)
    c.request(method, path, json.dumps(body) if body is not None else None, h)
    r = c.getresponse()
    raw = r.read()
    c.close()
    return r.status, raw


def post(d, path, body, **kw):
    status, raw = call(d, "POST", path, body, **kw)
    return status, json.loads(raw)


def page(d):
    status, raw = call(d, "GET", "/")
    assert status == 200
    html = raw.decode("utf-8")
    block = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    obj = json.loads(block)
    return {x["id"]: x for x in obj["invoices"]}, obj


def rows(data):
    p = data / "decisions.csv"
    return list(csv.DictReader(open(p, encoding="utf-8", newline=""))) if p.exists() else []


def by_verdict(data, verdict):
    return [r["invoice"] for r in server.list_invoices(folder=str(data))["invoices"]
            if server.check_invoice(r["invoice"], folder=str(data))["verdict"] == verdict]


def letters(data):
    return next((data / "output").glob("all-*")) / "letters"


def test_security_checks(data, dash):
    d = dash()
    body = {"invoice": by_verdict(data, "approve")[0], "decision": "approve"}
    assert call(d, "POST", "/api/decision", body, token=False)[0] == 403
    assert call(d, "POST", "/api/decision", body, headers={"X-Token": "wrong"})[0] == 403
    assert call(d, "POST", "/api/decision", body, headers={"Host": "evil.example:80"})[0] == 403
    assert call(d, "GET", "/api/ping", headers={"Host": "evil.example"})[0] == 403
    assert call(d, "GET", "/", headers={"Host": "evil.example"})[0] == 403
    assert call(d, "POST", "/api/decision", body, headers={"Origin": "http://evil.example"})[0] == 403
    assert call(d, "POST", "/api/decision", body, headers={"Origin": "null"})[0] == 403
    assert rows(data) == []
    assert call(d, "POST", "/api/decision", body, headers={"Origin": f"http://127.0.0.1:{d.port}"})[0] == 200
    assert call(d, "GET", "/api/ping")[0] == 200


def test_validation(data, dash):
    d = dash()
    inv = by_verdict(data, "dispute")[0]
    change = {"invoice": inv, "decision": "change", "verdict": "dispute", "reason": "r"}
    bad = [{"invoice": "nope", "decision": "approve"},
           {"invoice": "../x", "decision": "approve"},
           {"invoice": inv, "decision": "delete"},
           {**change, "amount": "1.234"}, {**change, "amount": "-1"}, {**change, "amount": "abc"},
           {**change, "amount": "999999"}, {**change, "reason": "x" * 501},
           {"invoice": inv, "decision": "change", "verdict": "hold"}]
    for b in bad:
        assert post(d, "/api/decision", b)[0] == 400, b
    assert rows(data) == []


def test_approve_change_and_undo(data, dash):
    d = dash()
    inv = by_verdict(data, "dispute")[0]
    status, out = post(d, "/api/decision", {"invoice": inv, "decision": "dispute"})
    assert status == 200 and out["row"]["overrule"] == "no" and len(rows(data)) == 1
    assert (letters(data) / f"{inv}.txt").exists()
    change = {"invoice": inv, "decision": "change", "verdict": "dispute", "amount": "45.00"}
    assert post(d, "/api/decision", change)[0] == 400 and len(rows(data)) == 1
    status, out = post(d, "/api/decision", {**change, "reason": "Sanne: old rate agreed by phone"})
    assert status == 200 and out["row"]["overrule"] == "yes" and out["row"]["amount_excl_vat"] == "45.00"
    assert rows(data)[-1]["reason"] == "Sanne: old rate agreed by phone"
    assert "EUR 45,00 excl. btw" in (letters(data) / f"{inv}.txt").read_text(encoding="utf-8")
    status, out = post(d, "/api/decision", {"invoice": inv, "decision": "undo"})
    assert status == 200 and len(rows(data)) == 3 and rows(data)[-1]["decision"] == "undo"
    assert page(d)[0][inv]["decision"] is None
    assert not (letters(data) / f"{inv}.txt").exists()
    concept = (letters(data) / f"{inv}.CONCEPT.txt").read_text(encoding="utf-8")
    assert "EUR 45,00 excl. btw" not in concept and concept.startswith("Aan: ")
    assert post(d, "/api/decision", {"invoice": inv, "decision": "undo"})[0] == 400


def test_letter_save(data, dash):
    d = dash()
    inv = by_verdict(data, "dispute")[0]
    text = "Aan: test\n\nMijn eigen tekst.\n"
    assert post(d, "/api/letter", {"invoice": inv, "text": text})[0] == 200
    assert (letters(data) / f"{inv}.CONCEPT.txt").read_text(encoding="utf-8") == text
    other = by_verdict(data, "approve")[0]
    assert post(d, "/api/decision", {"invoice": other, "decision": "approve"})[0] == 200
    assert (letters(data) / f"{inv}.CONCEPT.txt").read_text(encoding="utf-8") == text  # her edit survives
    assert page(d)[0][inv]["letter"]["saved"] == text
    for bad in ("../x", "..\\x", "", "a/b"):
        assert post(d, "/api/letter", {"invoice": bad, "text": text})[0] == 400
    assert post(d, "/api/letter", {"invoice": inv, "text": ""})[0] == 400
    assert post(d, "/api/letter", {"invoice": other, "text": text})[0] == 400  # approved: no letter file
    assert not list(data.glob("x*")) and not list((data / "output").glob("x*"))


def test_persistence_across_restart(data, dash):
    d = dash()
    inv = by_verdict(data, "approve")[0]
    post(d, "/api/decision", {"invoice": inv, "decision": "approve"})
    before, _ = page(d)
    d.stop()
    d2 = dash()
    after, obj = page(d2)
    assert after[inv]["decision"]["d"] == "pay" == before[inv]["decision"]["d"]
    assert obj["live"]["token"] == d2.token != d.token


def test_overrule_warning_on_card(data, dash):
    d = dash()
    groups = {}
    for i in by_verdict(data, "dispute") + by_verdict(data, "hold"):
        groups.setdefault(server.check_invoice(i, folder=str(data))["contractor"], []).append(i)
    for i in sum(groups.values(), []):
        post(d, "/api/decision", {"invoice": i, "decision": "change", "verdict": "approve", "reason": "ok"})
    counts = {}
    for x in rows(data):
        for k in x["rules"].split():
            counts[(x["contractor"], k)] = counts.get((x["contractor"], k), 0) + 1
    if max(counts.values()) < 3:
        pytest.skip("sample has no contractor and rule with 3 overrules")
    shown = [x for x in page(d)[0].values() if x["warn"]]
    assert shown and all("overrules for" in w for x in shown for w in x["warn"])


def test_file_render_is_read_only(data):
    html = next((data / "output").glob("all-*/review.html")).read_text(encoding="utf-8")
    block = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1)
    assert "live" not in json.loads(block) and "token" not in block
    # the decision controls are built only when LIVE: D.live present and an http page
    assert "LIVE=!!(D.live&&location.protocol.indexOf('http')===0)" in html


def test_no_free_port(data, dash):
    a = dash()
    b = dashboard.Dashboard(server, ports=[a.port])
    with pytest.raises(OSError, match="No free port"):
        b.serve(data)


def test_decided_amount_replaces_proposal_everywhere(data, dash):
    d = dash()
    inv = next(i for i in by_verdict(data, "dispute")
               if server.check_invoice(i, folder=str(data))["total_disputed_excl_vat"] not in (0, "0.00"))
    proposal = page(d)[0][inv]
    amount = "1.00"
    assert post(d, "/api/decision", {"invoice": inv, "decision": "disagree", "verdict": "dispute",
                                     "reason": "r", "amount": amount})[0] == 200
    items, obj = page(d)
    assert items[inv]["ex"] == "1.00" and items[inv]["proposal_ex"] == proposal["ex"]
    assert obj["total_ex"] == f"{sum(float(x['ex']) for x in obj['invoices']):.2f}"


def test_page_script_rules(data, dash):
    html = call(dash(), "GET", "/")[1].decode("utf-8")
    assert "Write a reason." in html and "How we read the contract here" in html
    assert "Close dispute: corrected invoice received" in html
    assert "'Replaces '" not in html  # no Replaces banner on the replacement
    assert "if(v.carried&&LIVE&&v.month)goTo" in html
    assert "keepTop" in html and "mouseenter" in html
    assert "hold=D.invoices.filter(function(v){return st(v)==='on_hold'})" in html


def test_flat_folder_month_roundtrip(data, monkeypatch):
    """check_all(month) on a flat folder offers a month the dashboard accepts and serves the same 40 invoices."""
    monkeypatch.setenv("OOSTERVELDE_NO_BROWSER", "1")
    d = dashboard.Dashboard(server, ports=(0,))
    monkeypatch.setattr(server, "_dash", d)
    try:
        assert "2026-01" in server.month_options(data) and "all" in server.month_options(data)
        r = server.check_all(month="2026-01", folder=str(data))
        assert r["run"].startswith("2026-01-")
        served = server.open_dashboard(folder=str(data), month="2026-01")
        assert served["url"].endswith("?month=2026-01") and d.port != 8766
        assert len(page(d)[0]) == 40
        status, raw = call(d, "GET", "/?month=all")
        assert status == 200 and len(page(d)[0]) == 40
        assert server.check_all(month="all", folder=str(data))["run"].startswith("all-")
        for bad in (lambda: server.check_all(month="1999-01", folder=str(data)),
                    lambda: server.open_dashboard(folder=str(data), month="1999-01"),
                    lambda: server.list_invoices(month="1999-01", folder=str(data))):
            with pytest.raises(ValueError, match="unknown month"):
                bad()
    finally:
        d.stop()
