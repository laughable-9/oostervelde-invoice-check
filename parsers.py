"""Parse contractor invoices (layouts b, h, j, w) into Decimal-based dataclasses."""
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

MONTHS = {m: i for i, m in enumerate(
    "januari februari maart april mei juni juli augustus september oktober november december".split(), 1)}
MONEY = r"-?[\d.]+,\d{2}"
WO_RE = re.compile(r"WO-\d{2}-\d{4}")
VAT_RE = re.compile(rf"BTW (\d+)% over ({MONEY}): ({MONEY})")


class ParseError(ValueError):
    """Raised for an unrecognised layout or a missing field; the caller holds the invoice."""


@dataclass
class Line:
    no: int
    description: str
    qty: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    vat_rate: Decimal  # percent, e.g. Decimal("21")
    raw: str
    code: str | None = None  # filled in by rules.classify; invoices carry no list codes


@dataclass
class VatBlock:
    rate: Decimal
    base: Decimal
    amount: Decimal


@dataclass
class Invoice:
    id: str  # file stem, e.g. "h-2026-0031"
    layout: str
    contractor: str
    number: str
    date: date
    wo: str
    address: str
    exec_date: date
    lines: list[Line]
    subtotal: Decimal
    vat: list[VatBlock]
    total: Decimal
    credit_ref: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def is_credit(self) -> bool:
        return self.credit_ref is not None

    @property
    def vat_total(self) -> Decimal:
        return sum((b.amount for b in self.vat), Decimal("0"))


def money(s: str) -> Decimal:
    return Decimal(s.replace(".", "").replace(",", "."))


def dmy(s: str) -> date:
    d, m, y = re.split(r"[-/]", s)
    return date(int(y), int(m), int(d))


def dutch_date(s: str) -> date:
    d, m, y = s.split()
    return date(int(y), MONTHS[m.lower()], int(d))


def find(pattern: str, text: str, what: str) -> re.Match:
    m = re.search(pattern, text, re.M)
    if not m:
        raise ParseError(f"missing {what}")
    return m


def parse_h(text: str):
    lines = []
    table = re.search(r"^-{20,}\n(.*?)^-{20,}", text, re.M | re.S)
    if not table:
        raise ParseError("missing line table")
    row = re.compile(rf"^(.+?)\s{{2,}}(-?[\d,]+) (\S.*?)\s{{2,}}({MONEY})\s+({MONEY})$")
    for raw in table.group(1).splitlines():
        if not raw.strip():
            continue
        m = row.match(raw)
        if not m:
            raise ParseError(f"unreadable line: {raw.strip()}")
        lines.append((raw.strip(), m.group(1), m.group(2), m.group(3), m.group(4), m.group(5), None))
    ref = re.search(r"^Betreft creditering van factuur (\S+)", text, re.M)
    return dict(
        contractor="Hoekstra",
        number=find(r"^Factuurnummer:\s*(\S+)", text, "invoice number").group(1),
        date=dmy(find(r"^Factuurdatum:\s*(\S+)", text, "invoice date").group(1)),
        wo=find(r"^Uw werkorder:\s*(\S+)", text, "work order").group(1),
        address=find(r"^Adres uitvoering:\s*(.+)$", text, "address").group(1).strip(),
        exec_date=dmy(find(r"^Datum uitvoering:\s*(\S+)", text, "execution date").group(1)),
        subtotal=money(find(rf"^Subtotaal excl\. BTW:\s*({MONEY})", text, "subtotal").group(1)),
        total=money(find(rf"^TOTAAL TE BETALEN: EUR ({MONEY})", text, "total").group(1)),
        credit_ref=ref.group(1) if ref else None,
        lines=lines,
    )


def parse_b(text: str):
    row = re.compile(rf"^\s*\d+\.\s+(.+?)\s*\|\s*(-?[\d,]+) (\S+)\s*\|\s*a\s+({MONEY})\s*\|\s*({MONEY})\s*$")
    lines = [(m.group(0).strip(), *m.groups(), None) for m in map(row.match, text.splitlines()) if m]
    head = find(r"^FACTUUR\s+nr\. (\S+)\s+datum (\d{4})-(\d{2})-(\d{2})", text, "invoice header")
    ex = find(r"^Uitvoeringsdatum: (\d{4})-(\d{2})-(\d{2})", text, "execution date")
    ref = re.search(r"^Betreft creditering van factuur (\S+)", text, re.M)
    return dict(
        contractor="Bosman",
        credit_ref=ref.group(1) if ref else None,
        number=head.group(1),
        date=date(*map(int, head.groups()[1:])),
        wo=find(r"\(werkorder (WO-\d{2}-\d{4})\)", text, "work order").group(1),
        address=find(r"^Locatie: (.+)$", text, "address").group(1).strip(),
        exec_date=date(*map(int, ex.groups())),
        subtotal=money(find(rf"^\s*netto\s+({MONEY})", text, "subtotal").group(1)),
        total=money(find(rf"^\s*totaal\s+({MONEY})", text, "total").group(1)),
        lines=lines,
    )


def parse_j(text: str):
    row = re.compile(rf"^(\S.*)\n\s+(-?[\d,]+) (\S+) @ ({MONEY}) -> ({MONEY})$", re.M)
    lines = [(f"{m.group(1)} / {m.group(0).splitlines()[1].strip()}", *m.groups(), None)
             for m in row.finditer(text)]
    head = find(r"^FACTUUR (\S+) \((\d{2}/\d{2}/\d{4})\)", text, "invoice header")
    bon = find(r"^Werkbon: (WO-\d{2}-\d{4}), (.+), uitgevoerd op (\d{2}/\d{2}/\d{4})", text, "work order")
    return dict(
        contractor="Jansen",
        number=head.group(1),
        date=dmy(head.group(2)),
        wo=bon.group(1),
        address=bon.group(2).strip(),
        exec_date=dmy(bon.group(3)),
        subtotal=money(find(rf"^Subtotaal: ({MONEY})", text, "subtotal").group(1)),
        total=money(find(rf"^Totaal: EUR ({MONEY})", text, "total").group(1)),
        lines=lines,
    )


def parse_w(text: str):
    row = re.compile(rf"^- (.+): (-?[\d,]+) (.+?) x EUR ({MONEY}) = EUR ({MONEY}) \((\d+)% btw\)$")
    lines = [(m.group(0).strip(), *m.groups()) for m in map(row.match, text.splitlines()) if m]
    work = find(r"^Werkzaamheden (.+), uitgevoerd (\d{1,2} \w+ \d{4})", text, "execution line")
    return dict(
        contractor="De Wit",
        number=find(r"^FACTUUR (\S+)", text, "invoice number").group(1),
        date=dutch_date(find(r"^\w+, (\d{1,2} \w+ \d{4})$", text, "invoice date").group(1)),
        wo=find(r"^Opdracht: (\S+)", text, "work order").group(1),
        address=work.group(1).strip(),
        exec_date=dutch_date(work.group(2)),
        subtotal=money(find(rf"^Totaal excl\. btw EUR ({MONEY})", text, "subtotal").group(1)),
        total=money(find(rf"^Totaal incl\. btw EUR ({MONEY})", text, "total").group(1)),
        lines=lines,
    )


LAYOUTS = [
    ("Installatiebedrijf Hoekstra", "h", parse_h),
    ("Schilderwerken De Wit", "w", parse_w),
    ("DAKWERKEN BOSMAN", "b", parse_b),
    ("Elektro Jansen", "j", parse_j),
]


def parse_invoice(path) -> Invoice:
    path = Path(path)
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    first = next((l for l in text.splitlines() if l.strip()), "")
    for marker, layout, fn in LAYOUTS:
        if first.startswith(marker):
            break
    else:
        raise ParseError(f"{path.name}: unrecognised invoice layout (first line: {first[:60]!r})")
    try:
        f = fn(text)
    except ParseError as e:
        raise ParseError(f"{path.name}: {e}") from None
    if not f["lines"]:
        raise ParseError(f"{path.name}: no invoice lines found")
    if not WO_RE.fullmatch(f["wo"]):
        raise ParseError(f"{path.name}: unreadable work order {f['wo']!r}")
    vat = [VatBlock(Decimal(r), money(b), money(a)) for r, b, a in VAT_RE.findall(text)]
    if not vat:
        raise ParseError(f"{path.name}: no VAT lines found")
    if any(rate is None for *_, rate in f["lines"]) and len(vat) != 1:
        raise ParseError(f"{path.name}: several VAT rates but no rate per line")
    lines = [
        Line(i, desc.strip(), money(q) if "," in q else Decimal(q), unit.strip(), money(p), money(a),
             Decimal(rate) if rate else vat[0].rate, raw)
        for i, (raw, desc, q, unit, p, a, rate) in enumerate(f.pop("lines"), 1)
    ]
    return Invoice(id=path.stem, layout=layout, lines=lines, vat=vat,
                   credit_ref=f.pop("credit_ref", None), **f)
