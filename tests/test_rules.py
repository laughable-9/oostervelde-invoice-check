import json
import sys
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import parsers  # noqa: E402
import rules  # noqa: E402

FILES = sorted((ROOT / "invoices").glob("*.txt"))
EXPECTED = json.loads((ROOT / "tests" / "expected.json").read_text(encoding="utf-8"))
TOTAL_FIELDS = ["total_disputed_excl_vat", "total_vat_effect", "total_disputed_incl_vat"]
FINDING_FIELDS = ["rule", "decision", "line", "line_text", "disputed_excl_vat", "vat_effect", "disputed_incl_vat"]


@pytest.fixture(scope="module")
def results():
    ctx = rules.load_context(ROOT)
    invoices = [parsers.parse_invoice(f) for f in FILES]
    return {r.invoice + ".txt": r for r in rules.check_all(invoices, ctx, [])}


def as_json(value):
    return f"{value:.2f}" if isinstance(value, Decimal) else value


def test_expected_covers_all_invoices(results):
    assert sorted(EXPECTED["invoices"]) == sorted(results) == sorted(f.name for f in FILES)


@pytest.mark.parametrize("name", sorted(EXPECTED["invoices"]))
def test_expected(results, name):
    # Every field except the free-text "issue" (hand-check wording) and "status".
    exp, got = EXPECTED["invoices"][name], results[name]
    assert got.verdict == exp["verdict"]
    assert as_json(got.total_disputed_excl_vat) == exp["total_disputed_excl_vat"]
    assert as_json(got.total_disputed_incl_vat) == exp["total_disputed_incl_vat"]
    assert got.dispute_by == exp.get("dispute_by")
    got_findings = [{k: as_json(getattr(f, k)) for k in FINDING_FIELDS} for f in got.findings]
    assert got_findings == [{k: f[k] for k in FINDING_FIELDS} for f in exp["findings"]]
    assert all(f.line_text for f in got.findings)


def test_totals(results):
    got = {k: as_json(sum((getattr(r, k) for r in results.values()), Decimal(0))) for k in TOTAL_FIELDS}
    assert got == EXPECTED["totals"]


def test_payable_never_above_invoice_total(results):
    assert all(r.payable_incl_vat <= parsers.parse_invoice(ROOT / "invoices" / name).total
               for name, r in results.items())


def test_q7_mixed_invoice_allocation():
    # Synthetic: h-2026-0061 (both lines at 9%, 21% due) with line 2 also billed above the list price.
    ctx = rules.load_context(ROOT)
    inv = parsers.parse_invoice(ROOT / "invoices" / "h-2026-0061.txt")
    l2 = inv.lines[1]
    extra = Decimal("10.00") * l2.qty
    lines = [inv.lines[0], replace(l2, unit_price=l2.unit_price + 10, amount=l2.amount + extra)]
    vat = [replace(inv.vat[0], base=inv.vat[0].base + extra, amount=rules.r2((inv.vat[0].base + extra) * 9 / 100))]
    inv = replace(inv, lines=lines, vat=vat, subtotal=inv.subtotal + extra, total=inv.subtotal + extra + vat[0].amount)
    res = rules.check_invoice(inv, ctx)
    assert res.verdict == "dispute"
    q7 = [f for f in res.findings if f.decision == "Q7"]
    assert len(q7) == 2 and all(f.disputed_incl_vat == f.vat_effect == 0 for f in q7)
    r1 = next(f for f in res.findings if f.rule == "R1")
    assert r1.disputed_excl_vat == extra and r1.vat_effect == rules.r2(extra * 9 / 100)  # at the rate charged
    assert res.total_vat_effect == sum(f.vat_effect for f in res.findings)
    assert res.payable_incl_vat == inv.total - res.total_disputed_incl_vat <= inv.total


def test_all_invoices_parse_and_add_up():
    assert len(FILES) == 40
    mismatches = []
    for f in FILES:
        inv = parsers.parse_invoice(f)
        line_sum = sum(l.amount for l in inv.lines)
        if line_sum != inv.subtotal:
            mismatches.append(f"{inv.id}: lines {line_sum} vs subtotal {inv.subtotal}")
        for b in inv.vat:
            base = sum(l.amount for l in inv.lines if l.vat_rate == b.rate)
            vat = (b.base * b.rate / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
            if base != b.base or vat != b.amount:
                mismatches.append(f"{inv.id}: VAT {b.rate}% block")
        if inv.subtotal + inv.vat_total != inv.total:
            mismatches.append(f"{inv.id}: subtotal + VAT {inv.subtotal + inv.vat_total} vs total {inv.total}")
    print("\n".join(mismatches))
    # These are findings on the invoices (R19), not parser bugs.
    assert mismatches == ["h-2026-0052: subtotal + VAT 410.20 vs total 510.20"]


def test_unknown_layout_raises(tmp_path):
    bad = tmp_path / "x.txt"
    bad.write_text("Some Other Contractor\nFACTUUR 1\n", encoding="utf-8")
    with pytest.raises(parsers.ParseError, match="unrecognised invoice layout"):
        parsers.parse_invoice(bad)
