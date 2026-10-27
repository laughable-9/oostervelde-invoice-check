import re
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import rules  # noqa: E402
import server  # noqa: E402

QUOTED = re.compile(r'"[^"]*"')
EN_WORDS = re.compile(r"\b(invoice|invoices|line|lines|work order|disputed|the|please|credit note)\b", re.I)
NL_WORDS = re.compile(r"regulier werk|werkorder|voorrijkosten|factuur|regel\b|betwist|prijslijst|btw\b", re.I)


@pytest.fixture
def data(tmp_path):
    for name in ("price-agreement-2025.csv", "work-orders-export.csv", "contract-excerpt.md"):
        shutil.copy(ROOT / name, tmp_path / name)
    shutil.copytree(ROOT / "invoices", tmp_path / "invoices")
    return tmp_path


def all_letters(data, amount=None):
    """(invoice id, Dutch, English) for every invoice that has a letter finding, plus the whole-invoice letter."""
    invoices, results, _ = server.run_checks(data)
    ctx = rules.load_context(data)
    inv = {i.id: i for i in invoices}
    out = []
    for r in results:
        i = inv[r.invoice]
        if server.letter_findings(r):
            out.append((r.invoice, server.letter(i, r, ctx), server.letter_en(i, r, ctx)))
        out.append((r.invoice + " full", server.letter_full(i, r), server.letter_full_en(i, r)))
    return out


def outside_quotes(text):
    return QUOTED.sub("", text)


def test_letters_have_no_pipes_and_no_leaks(data):
    letters = all_letters(data)
    assert len(letters) > 20
    for name, nl, en in letters:
        for t in (nl, en):
            assert "|" not in t and chr(0x2014) not in t and not re.search(r"\b[RQ]\d", t), name
        assert not EN_WORDS.search(outside_quotes(nl)), (name, EN_WORDS.search(outside_quotes(nl)).group())
        assert not NL_WORDS.search(outside_quotes(en)), (name, NL_WORDS.search(outside_quotes(en)).group())
        assert "In English:" in en or "Artikel" not in nl, name


def test_letter_quotes_are_verbatim_in_both_languages(data):
    contract = re.sub(r"\s+", " ", (data / "contract-excerpt.md").read_text(encoding="utf-8"))
    src = {p.stem: re.sub(r"\s+", " ", p.read_text(encoding="utf-8")) for p in (data / "invoices").glob("*.txt")}
    for name, nl, en in all_letters(data):
        for t in (nl, en):
            for q in re.findall(r'"([^"]+)"', t):
                q = re.sub(r"\s+", " ", q)
                assert q in contract or q in src[name.split(" ")[0]], (name, q)


def test_override_letter_shows_overview_with_her_amount(data):
    server.check_all(folder=str(data))
    out = server.record_decision("b-B-26-0102", "letter_ok", amount_excl_vat="45.00", reason="Sanne: partial", folder=str(data))
    text = (data / out["letter_ready"]).read_text(encoding="utf-8")
    assert "Overzicht" in text and "EUR 54,45 incl. btw" in text
    assert "Betwist:       EUR 46,44" not in text and "Reden:" in text and "Gefactureerd:" in text
    assert "Regel 4: Voorrijkosten spoed" in text and "EUR 1.772,43 incl. btw" in text


def test_undercharged_vat_letter_asks_for_corrected_invoice(data):
    inv = {x[0]: x for x in all_letters(data)}["h-2026-0061"]
    nl, en = inv[1], inv[2]
    assert "Overzicht" not in nl and "Berekend tarief:  9% btw" in nl and "Juist tarief:" in nl
    assert "Wij verzoeken u een gecorrigeerde factuur te sturen met het juiste btw-tarief." in nl
    assert "We ask you to send a corrected invoice with the right VAT rate." in en
    assert "creditfactuur" not in nl


def test_english_dates_and_numbers(data):
    en = {x[0]: x[2] for x in all_letters(data)}["b-B-26-0102"]
    assert "Re: invoice B-26-0102 of 15 January 2026, work order WO-26-1005" in en
    assert 'Line 4: "Voorrijkosten spoed"' in en and "In English:" in en and "EUR 1.826,88 incl. VAT" in en


def test_vat_rate_reason_depends_on_the_line(data):
    inv = {x[0]: x for x in all_letters(data)}["h-2026-0061"]
    nl, en = inv[1], inv[2]
    painting = "het verlaagde tarief van 9 procent alleen geldt voor schilderarbeid (prijslijstcodes W01 en W04)"
    assert painting in nl and "ouder is dan twee jaar" not in nl and "woningen ouder dan twee jaar" not in nl
    assert "only applies to painting labour (price list codes W01 and W04)" in en
    assert "op materiaal geldt 21 procent" in nl and "on material 21 percent applies" in en
