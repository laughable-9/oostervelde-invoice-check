import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import parsers  # noqa: E402
import rules  # noqa: E402

FILES = sorted((ROOT / "invoices").glob("*.txt"))
QUOTE = re.compile(r"'([^']+)'|\"([^\"]+)\"|‘([^’]+)’|“([^”]+)”")


def ws(s):
    return re.sub(r"\s+", " ", s).strip()


def read(p):
    return ws(Path(p).read_text(encoding="utf-8"))


def test_every_quote_is_verbatim():
    ctx = rules.load_context(ROOT)
    invoices = [parsers.parse_invoice(f) for f in FILES]
    shared = [read(ROOT / n) for n in ("contract-excerpt.md", "price-agreement-2025.csv", "work-orders-export.csv")]
    sources = {f.stem: read(f) for f in FILES}
    checked, bad = 0, []
    for r in rules.check_all(invoices, ctx, []):
        for f in r.findings:
            for m in QUOTE.finditer(f.evidence):
                q = ws(next(g for g in m.groups() if g))
                checked += 1
                if not any(q in s for s in shared + [sources[r.invoice]]):
                    bad.append((r.invoice, f.rule, q))
    for b in bad:
        print("NOT VERBATIM:", b)
    print("quotes checked:", checked)
    assert checked > 0 and not bad


def test_plain_refs_quote_the_contract_verbatim():
    import server  # noqa: E402
    contract = read(ROOT / "contract-excerpt.md")
    ctx = rules.load_context(ROOT)
    invoices = [parsers.parse_invoice(f) for f in FILES]
    quotes = [q for _, _, q in rules.REFS.values()]
    for inv, r in zip(invoices, rules.check_all(invoices, ctx, [])):
        quotes += [x["quote"] for f in r.findings for x in server.refs_for(rules.RULE_REFS.get(f.rule, []))]
        quotes += [x["quote"] for rd in server.readings(r) for x in rd["refs"]]
    bad = [q for q in quotes if ws(q) not in contract]
    assert len(quotes) > len(rules.REFS) and not bad, bad
