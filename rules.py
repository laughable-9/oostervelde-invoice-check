"""Article 4 checks (rulebook R0 to R20, decisions Q1 to Q21). Pure functions; reads reference data only in load_context."""
import csv
import os
import re
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from parsers import Invoice, Line, VatBlock

D0 = Decimal("0.00")
CENT = Decimal("0.01")
INDEX_2026 = Decimal("1.032")
LAST_2025_DAY = date(2025, 12, 31)
MEERWERK_FREE = Decimal("250.00")
SMALL_LIMIT = Decimal("25.00")
HIGH_LIMIT = Decimal("100.00")
LABOUR = {"H02", "W01", "B01", "J01"}
CALLOUT = {"H06", "B05", "J05"}
PAINT_LABOUR = {"W01", "W04"}
BROKEN_TOTALS = {"R11", "R18", "R19"}

ART = {
    "4.1": "Art. 4.1: 'Alle prijzen zijn exclusief btw en staan in de prijslijst' and 'De eenheid in de prijslijst is leidend.'",
    "4.2": "Art. 4.2: 'Bepalend is de datum van uitvoering van het werk, niet de factuurdatum.'",
    "4.3": "Art. 4.3: 'Voorrijkosten worden alleen vergoed bij werkorders van het type spoed, en ten hoogste één keer per werkorder.'",
    "4.4": "Art. 4.4: 'Uren daarboven worden alleen vergoed als Woonkring Oostervelde vooraf extra uren heeft goedgekeurd.'",
    "4.5a": "Art. 4.5: 'Zonder akkoord wordt het meerwerk boven EUR 250,00 niet vergoed, ook niet het deel tot EUR 250,00.'",
    "4.5b": "Art. 4.5: 'Met akkoord wordt ten hoogste het goedgekeurde bedrag vergoed.'",
    "4.6": "Art. 4.6: 'het verlaagde tarief van 9 procent, uitsluitend over de arbeid (prijslijstcodes W01 en W04)' and 'Op materiaal en op alle overige werkzaamheden geldt 21 procent.'",
    "4.7": "Art. 4.7: 'Leveringen of werkzaamheden die niet in de prijslijst staan en niet als meerwerk zijn vermeld, worden alleen vergoed na voorafgaand akkoord van Woonkring Oostervelde.'",
    "4.8a": "Art. 4.8: 'Elke werkorder wordt één keer gefactureerd.'",
    "4.8b": "Art. 4.8: 'Woonkring Oostervelde verrekent de creditfactuur met die factuur.'",
    "4.9": "Art. 4.9: 'Een factuur zonder geldige werkorder van Woonkring Oostervelde wordt niet betaald tot de opdracht is bevestigd.'",
}

# Plain-language references: key -> (label, one plain English sentence, verbatim contract text).
REFS = {
    "4.1": ("Art. 4.1", "Prices are the ones in the agreed price list, excluding VAT.",
            "Alle prijzen zijn exclusief btw en staan in de prijslijst"),
    "4.1u": ("Art. 4.1", "A price billed in another unit is converted to the price list unit and may not come out higher.",
             "De eenheid in de prijslijst is leidend. Factureert de opdrachtnemer in een andere eenheid, dan wordt de "
             "prijs per eenheid omgerekend naar de prijslijst en mag deze niet hoger uitkomen."),
    "4.2": ("Art. 4.2", "The date the work was done decides which year's prices apply, not the invoice date.",
            "Bepalend is de datum van uitvoering van het werk, niet de factuurdatum."),
    "4.3": ("Art. 4.3", "A call-out fee is only paid on urgent jobs, and at most once per job.",
            "Voorrijkosten worden alleen vergoed bij werkorders van het type spoed, en ten hoogste één keer per werkorder."),
    "4.4": ("Art. 4.4", "Hours above the job's maximum are only paid when extra hours were approved in advance.",
            "Uren daarboven worden alleen vergoed als Woonkring Oostervelde vooraf extra uren heeft goedgekeurd."),
    "4.5a": ("Art. 4.5", "Extra work above 250 euros without written approval is not paid at all.",
             "Zonder akkoord wordt het meerwerk boven EUR 250,00 niet vergoed, ook niet het deel tot EUR 250,00."),
    "4.5b": ("Art. 4.5", "With approval, extra work is paid up to the approved amount and no more.",
             "Met akkoord wordt ten hoogste het goedgekeurde bedrag vergoed."),
    "4.6": ("Art. 4.6", "The 9 percent VAT rate is only for painting labour on homes older than two years; "
                        "everything else is 21 percent.",
            "Op schilderwerk aan woningen die ouder zijn dan twee jaar geldt het verlaagde tarief van 9 procent, "
            "uitsluitend over de arbeid (prijslijstcodes W01 en W04). Op materiaal en op alle overige werkzaamheden "
            "geldt 21 procent."),
    "4.7": ("Art. 4.7", "Items that are not on the price list and not marked as extra work are only paid with prior approval.",
            "Leveringen of werkzaamheden die niet in de prijslijst staan en niet als meerwerk zijn vermeld, worden "
            "alleen vergoed na voorafgaand akkoord van Woonkring Oostervelde."),
    "4.8a": ("Art. 4.8", "Each job may be invoiced only once.", "Elke werkorder wordt één keer gefactureerd."),
    "4.8b": ("Art. 4.8", "Corrections come as a credit note that is offset against the original invoice.",
             "Correcties lopen via een creditfactuur die verwijst naar de oorspronkelijke factuur. Woonkring "
             "Oostervelde verrekent de creditfactuur met die factuur."),
    "4.9": ("Art. 4.9", "An invoice without a valid work order is not paid until the job is confirmed.",
            "Een factuur zonder geldige werkorder van Woonkring Oostervelde wordt niet betaald tot de opdracht is bevestigd."),
    "4.10": ("Art. 4.10", "A disputed invoice is reported in writing with a reason, and the undisputed part is paid.",
             "Betwiste facturen of factuurregels worden binnen 10 werkdagen schriftelijk en met reden aan de "
             "opdrachtnemer gemeld. Het onbetwiste deel wordt wel betaald."),
}
RULE_REFS = {"R1": ["4.1", "4.2"], "R3": ["4.1u"], "R4": ["4.3"], "R5": ["4.3"], "R6": ["4.4"], "R8": ["4.5a"],
             "R9": ["4.5b"], "R10": ["4.6"], "R12": ["4.7"], "R13": ["4.8a"], "R14": ["4.8b"], "R15": ["4.9"],
             "R16": ["4.9"]}
OPEN_DISPUTE = {"letter_ready", "waiting"}  # history statuses a credit note or corrected invoice can close
LINKABLE = OPEN_DISPUTE | {"resolved"}  # still linked after Sanne confirmed the outcome


def quoted(raw: str) -> str:
    """Quote an invoice line as printed: two-line layouts (joined with ' / ' by the parser) become two quotes."""
    head, sep, tail = raw.rpartition(" / ")
    return f"'{head}' and '{tail}'" if sep else f"'{raw}'"


def r2(x: Decimal) -> Decimal:
    return x.quantize(CENT, ROUND_HALF_UP)


def eur(x: Decimal) -> str:
    return f"{x:.2f}"


# ---------------------------------------------------------------- reference data

@dataclass
class PriceRow:
    code: str
    supplier: str
    description: str
    unit: str
    price_2025: Decimal


@dataclass
class WorkOrder:
    wo: str
    address: str
    supplier: str
    job: str
    type: str
    max_hours: Decimal
    mu: str
    mu_hours: Decimal
    ga: str
    ga_eur: Decimal | None
    built: int


@dataclass
class Context:
    prices: dict[str, PriceRow]
    work_orders: dict[str, WorkOrder]


INVOICE_FILES: dict[str, Path] = {}  # invoice id -> source file, set by a caller with another folder layout


def data_dir(path=None) -> Path:
    return Path(path or os.environ.get("OOSTERVELDE_DATA") or Path(__file__).resolve().parent)


def load_context(path=None) -> Context:
    d = data_dir(path)
    with open(d / "price-agreement-2025.csv", encoding="utf-8", newline="") as f:
        prices = {r["code"]: PriceRow(r["code"], r["supplier"], r["description"], r["unit"],
                                      Decimal(r["price_excl_vat_2025"])) for r in csv.DictReader(f)}
    with open(d / "work-orders-export.csv", encoding="utf-8", newline="") as f:
        wos = {r["wo"]: WorkOrder(
            r["wo"], r["address"], r["supplier"], r["job"], r["type"], Decimal(r["max_labor_hours"]),
            r["extra_hours_approval"], Decimal(r["approved_extra_hours"] or 0), r["meerwerk_approval"],
            Decimal(r["approved_meerwerk_eur"]) if r["approved_meerwerk_eur"] else None, int(r["built"]),
        ) for r in csv.DictReader(f)}
    return Context(prices, wos)


def applicable_price(row: PriceRow, exec_date: date) -> Decimal:
    # R2, Q1, Q2: execution date decides; 2026 price = 2025 x 1.032 rounded half up per list unit.
    return row.price_2025 if exec_date <= LAST_2025_DAY else r2(row.price_2025 * INDEX_2026)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def classify(line: Line, supplier: str, ctx: Context) -> str | None:
    """R0: list code, 'MEERWERK', 'CREDIT', or None for an off-list item."""
    if line.amount < 0 or line.qty < 0:
        return "CREDIT"
    if norm(line.description).startswith("meerwerk"):
        return "MEERWERK"
    for row in ctx.prices.values():
        if row.supplier == supplier and norm(row.description) == norm(line.description):
            return row.code
    return None


def unit_factor(billed: str, listed: str) -> Decimal | None:
    """List units per billed unit, or None when the units cannot be converted (R3)."""
    if norm(billed) == norm(listed):
        return Decimal(1)
    m = re.fullmatch(r"\w+ (\d+) (\w+)", norm(listed))  # e.g. "rol 25 m"
    if m and norm(billed) == m.group(2):
        return 1 / Decimal(m.group(1))
    return None


def vat_for(state: dict) -> Decimal:
    # Q8: VAT per rate base, rounded half up.
    bases: dict[Decimal, Decimal] = {}
    for amount, rate in state.values():
        bases[rate] = bases.get(rate, D0) + amount
    return sum((r2(b * rate / 100) for rate, b in bases.items()), D0)


def source_line(inv: Invoice, pattern: str, last: bool = False) -> str:
    """The invoice's own text line for an invoice-level finding (first or last line matching pattern).
    Reads <data dir>/invoices/<id>.txt; falls back to a description built from the parsed fields."""
    path = INVOICE_FILES.get(inv.id) or data_dir() / "invoices" / f"{inv.id}.txt"
    hits = []
    if path.is_file():
        hits = [t.strip() for t in path.read_text(encoding="utf-8").splitlines() if re.search(pattern, t, re.I)]
    if hits:
        return hits[-1] if last else hits[0]
    return f"Invoice {inv.number}, work order {inv.wo}, total EUR {eur(inv.total)}"


def wo_line(inv: Invoice) -> str:
    return source_line(inv, re.escape(inv.wo))


def add_working_days(d: date, n: int) -> date:
    while n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


# ---------------------------------------------------------------- results

@dataclass
class Finding:
    invoice: str
    line: int | None
    line_text: str
    rule: str
    decision: str | None
    issue: str
    evidence: str
    disputed_excl_vat: Decimal = D0
    vat_effect: Decimal = D0
    disputed_incl_vat: Decimal = D0
    small: bool = False
    provisional: bool = False
    hold: bool = False
    repeat: bool = False  # set by the caller: let go often enough before that it is no longer small
    repeat_count: int = 0


@dataclass
class Result:
    invoice: str
    contractor: str
    number: str
    wo: str
    verdict: str
    risk: str
    findings: list[Finding]
    interpretations: list[str]
    notes: list[str]
    total_disputed_excl_vat: Decimal
    total_vat_effect: Decimal
    total_disputed_incl_vat: Decimal
    payable_incl_vat: Decimal
    dispute_by: str | None  # ISO date, e.g. "2026-02-13"
    dispute_by_label: str = "estimate: invoice date + 10 working days (Mon-Fri), holidays not modelled (Q21)"
    linked_invoice: str | None = None  # earlier invoice this one credits or replaces (cross-month)
    link: dict | None = None  # {invoice, kind, match, remaining_incl_vat, proposed_status}
    readings: list[dict] = field(default_factory=list)  # per note: {text, plain, refs: [REFS keys]}


def _note(res_or_lists, text: str, plain: str, *refs: str) -> None:
    """Add an interpretation note with its plain-language reading. Accepts a Result or (notes, readings)."""
    notes, readings = (res_or_lists.notes, res_or_lists.readings) if isinstance(res_or_lists, Result) else res_or_lists
    notes.append(text)
    readings.append({"text": text, "plain": plain, "refs": list(refs)})


@dataclass
class _Pending:
    finding: Finding
    delta: Decimal = D0  # reduction of the line amount (excl. VAT)
    new_rate: Decimal | None = None
    fixed: tuple[Decimal, Decimal, Decimal] | None = None  # (excl, VAT, incl) set directly: R13, R18, R19


def check_invoice(inv: Invoice, ctx: Context, prior_meerwerk: Decimal = D0, confirmed: bool = False) -> Result:
    """Check one invoice on its own. prior_meerwerk: meerwerk already billed on this WO elsewhere (Q10).
    confirmed: Sanne recorded that the job behind an unknown work order is confirmed (Art. 4.9 hold lifted)."""
    pend: list[_Pending] = []
    interp: set[str] = set()
    notes: list[str] = []
    readings: list[dict] = []

    def add(rule, line, issue, evidence, decision=None, delta=D0, new_rate=None, fixed=None, hold=False, text=None):
        f = Finding(inv.id, line.no if line else None, line.description if line else text, rule, decision,
                    issue, (f"Invoice: {quoted(line.raw)}. " if line else "") + evidence, hold=hold)
        pend.append(_Pending(f, delta, new_rate, fixed))

    wo = ctx.work_orders.get(inv.wo)
    if wo is None and confirmed:
        _note((notes, readings), f"Work order {inv.wo} confirmed by Woonkring Oostervelde; the checks are final (Art. 4.9, Q16).",
              "The job was confirmed, so the checks below are final and no longer provisional.", "4.9")
    elif wo is None:
        add("R15", None, f"Work order {inv.wo} not in the work order export",
            f"{ART['4.9']} {inv.wo} is unknown; confirm the job with the housing officer.", "Q16", hold=True,
            text=wo_line(inv))
        # Q16: other checks still run and are shown as provisional.
    elif wo.supplier != inv.contractor or norm(wo.address) != norm(inv.address):
        add("R16", None, f"Work order {inv.wo} belongs to {wo.supplier}, {wo.address}",
            f"{ART['4.9']} Invoice: {inv.contractor}, {inv.address}.", hold=True, text=wo_line(inv))

    # R17 line arithmetic, R18 subtotal, R11 VAT blocks, R19 total
    line_sum = sum((l.amount for l in inv.lines), D0)
    for l in inv.lines:
        diff = l.amount - r2(l.qty * l.unit_price)
        if diff:
            add("R17", l, f"Line amount {eur(l.amount)} is not {l.qty} x {eur(l.unit_price)} = {eur(r2(l.qty * l.unit_price))}",
                f"Correct line amount {eur(r2(l.qty * l.unit_price))}, billed {eur(l.amount)}.", delta=max(diff, D0))
    if inv.subtotal != line_sum:
        d = inv.subtotal - line_sum
        add("R18", None, f"Subtotal {eur(inv.subtotal)} is not the sum of the lines {eur(line_sum)}",
            f"Sum of lines {eur(line_sum)}, stated {eur(inv.subtotal)}.", fixed=(d, D0, d),
            text=source_line(inv, r"subtota|^\s*netto|totaal excl"))
    for b in inv.vat:
        base = sum((l.amount for l in inv.lines if l.vat_rate == b.rate), D0)
        if b.base != base or b.amount != r2(b.base * b.rate / 100):
            add("R11", None, f"VAT {b.rate}% block {eur(b.base)}: {eur(b.amount)} does not compute",
                f"Lines at {b.rate}%: {eur(base)}; {b.rate}% of that = {eur(r2(base * b.rate / 100))}; stated {eur(b.amount)}.",
                "Q8", text=source_line(inv, rf"BTW {b.rate}% over"))
    expected_total = inv.subtotal + inv.vat_total
    if inv.total != expected_total:
        add("R19", None, f"Total {eur(inv.total)} is not subtotal plus VAT {eur(expected_total)}",
            f"{eur(inv.subtotal)} + {eur(inv.vat_total)} = {eur(expected_total)}, stated {eur(inv.total)}.",
            "Q18", fixed=(D0, D0, inv.total - expected_total),  # Q18: incl. VAT only
            text=source_line(inv, r"^\s*totaal", last=True))

    # Line checks: R0, R1, R2, R3, R4, R5, R6, R10, R12; meerwerk collected for R7 to R9.
    hours_left = None
    if wo:
        has_mu = bool(re.fullmatch(r"MU-\d{4}", wo.mu))
        hours_left = wo.max_hours + (wo.mu_hours if has_mu else D0)
    callouts_left = Decimal(1)
    meerwerk: list[Line] = []
    codes = {l.no: classify(l, inv.contractor, ctx) for l in inv.lines}
    hours_billed = sum((l.qty for l in inv.lines if codes[l.no] in LABOUR), D0)
    for l in inv.lines:
        code = codes[l.no]
        r17 = max(l.amount - r2(l.qty * l.unit_price), D0)
        if code == "CREDIT":
            continue
        if code == "MEERWERK":
            meerwerk.append(l)
        elif code is None:
            # Q17: off-list without meerwerk label: dispute the line, invite the contractor to show approval.
            add("R12", l, "Item not in the price list and not stated as meerwerk",
                f"{ART['4.7']} No prior approval found for {inv.wo}; send it if you have one.", "Q17",
                delta=l.amount - r17)
        else:
            row = ctx.prices[code]
            price = applicable_price(row, inv.exec_date)
            factor = unit_factor(l.unit, row.unit)
            if factor is None:
                # DECIDE: unconvertible unit is not covered by a Q decision; held as it cannot be checked (closest: Q16).
                add("R3", l, f"Billed unit '{l.unit}' cannot be converted to list unit '{row.unit}'",
                    f"{ART['4.1']} {code} list unit {row.unit}.", hold=True)
                continue
            conv = price * factor  # Q3: no intermediate rounding of the converted price
            billed = r2(l.qty * l.unit_price)
            r1 = max(billed - r2(l.qty * conv), D0)
            if r1:
                year = "2025" if inv.exec_date <= LAST_2025_DAY else "2026"
                if factor != 1:
                    add("R3", l, f"Billed {eur(l.unit_price)} per {l.unit}; list {eur(price)} per {row.unit} = {conv.normalize():f} per {l.unit}",
                        f"{ART['4.1']} {code} {row.description}: {eur(price)} per {row.unit} ({year}); allowed {l.qty} x {conv.normalize():f} = {eur(r2(l.qty * conv))}.",
                        "Q3", delta=r1)
                else:
                    q2 = "Q2" if inv.exec_date <= LAST_2025_DAY else None
                    add("R1", l, f"Billed {eur(l.unit_price)} instead of {year} list price {eur(price)} ({code}), {l.qty} x {eur(l.unit_price - price)}",
                        f"{ART['4.1']} {ART['4.2']} Executed {inv.exec_date:%d-%m-%Y}; {code} {row.description} {year} = {eur(price)}.",
                        q2, delta=r1)
            elif l.unit_price < conv:
                interp.add("Q4")  # Q4: a price below the list is not flagged
            if factor != 1:
                interp.add("Q3")
            # quantity limits (R4, R5, R6); stacking: correct = allowed qty x applicable price
            allowed = None
            if wo and code in CALLOUT:
                allowed = D0 if wo.type != "spoed" else min(l.qty, callouts_left)
                if wo.type == "spoed":
                    callouts_left -= allowed
            elif wo and code in LABOUR:
                allowed = min(l.qty, hours_left)
                hours_left -= allowed
            if allowed is not None and allowed < l.qty:
                rest = max(l.amount - r17 - r1 - r2(allowed * min(conv, l.unit_price)), D0)
                if code in CALLOUT and wo.type != "spoed":
                    add("R4", l, f"Call-out fee on regular ({wo.type}) work order {inv.wo}",
                        f"{ART['4.3']} {inv.wo} is type {wo.type}; bij regulier werk zijn voorrijkosten in de prijzen inbegrepen.",
                        delta=rest)
                elif code in CALLOUT:
                    add("R5", l, f"Second call-out fee on work order {inv.wo}",
                        f"{ART['4.3']} The invoice bills call-out more than once for {inv.wo}.", delta=rest)
                else:
                    extra = f" + {wo.mu}: {wo.mu_hours} h" if has_mu else ", no MU approval"
                    add("R6", l, f"{hours_billed} hours billed, {inv.wo} max {wo.max_hours}{extra}: {l.qty - allowed} x {eur(price)}",
                        f"{ART['4.4']} {inv.wo} max {wo.max_hours} h{extra}.", "Q12" if has_mu else "Q13", delta=rest)
            if "vast tarief" in norm(l.description) and hours_billed:
                interp.add("Q11")  # Q11: only labour lines count toward the hour maximum

        # R10 VAT rate (Q5, Q6, Q7)
        expected = Decimal(21)
        if code in PAINT_LABOUR:
            if not wo:
                _note((notes, readings), f"Line {l.no}: VAT rate cannot be verified without a build year (provisional, Q16).",
                      f"The VAT rate on line {l.no} cannot be checked, because the build year of the home is unknown.",
                      "4.6")
                continue
            age = inv.exec_date.year - wo.built
            if age == 2:
                # Q5: exactly two years by build year is uncertain: hold and ask.
                add("R10", l, f"Dwelling built {wo.built}, executed {inv.exec_date.year}: older than two years is uncertain",
                    f"{ART['4.6']} Bouwjaar {wo.built}.", "Q5", hold=True)
                continue
            expected = Decimal(9) if age >= 3 else Decimal(21)
            if expected == 9 and "trappenhuis" in norm(wo.job):
                interp.add("Q6")  # Q6: a stairwell of a residential building counts as woning
        if l.vat_rate != expected:
            under = l.vat_rate < expected
            built = f"dwelling built {wo.built}" if wo else "work order unknown"
            add("R10", l, f"Charged {l.vat_rate}% VAT, {expected}% applies ({built}); VAT {'under' if under else 'over'}-charged",
                f"{ART['4.6']} Code {code or 'n/a'}, {built}.", "Q7" if under else "Q8", new_rate=expected)

    # R7, R8, R9 meerwerk per work order (Q9, Q10)
    mw_total = sum((l.amount for l in meerwerk), D0)
    if meerwerk and wo:
        has_ga = bool(re.fullmatch(r"GA-\d{4}", wo.ga)) and wo.ga_eur is not None
        if has_ga:
            excess = max(mw_total - max(wo.ga_eur - prior_meerwerk, D0), D0)
            for l in reversed(meerwerk):
                part = min(excess, l.amount)
                if part:
                    add("R9", l, f"Meerwerk {eur(prior_meerwerk + mw_total)} on {inv.wo} above {wo.ga} approved {eur(wo.ga_eur)}",
                        f"{ART['4.5b']} {wo.ga}: EUR {eur(wo.ga_eur)}; billed EUR {eur(prior_meerwerk + mw_total)}.", "Q9", delta=part)
                    excess -= part
        elif prior_meerwerk + mw_total > MEERWERK_FREE:
            for l in meerwerk:
                add("R8", l, f"Meerwerk {eur(prior_meerwerk + mw_total)} on {inv.wo} above EUR 250.00 without GA approval",
                    f"{ART['4.5a']} {inv.wo} has no GA number.", "Q10", delta=l.amount)

    # Q8: a clean outcome that a per-line VAT method would break relies on the Q8 reading.
    if r2(sum((r2(l.amount * l.vat_rate / 100) for l in inv.lines), D0)) != inv.vat_total:
        interp.add("Q8")

    return _finish(inv, pend, interp, notes, readings)


def is_small(f: Finding, limit: Decimal = SMALL_LIMIT) -> bool:
    """Small: some money below the limit (excl. VAT, else incl.). A VAT-rate finding is never small."""
    basis = abs(f.disputed_excl_vat) or abs(f.disputed_incl_vat)
    return f.rule != "R10" and D0 < basis < limit


def _finish(inv: Invoice, pend: list[_Pending], interp: set[str], notes: list[str],
            readings: list[dict] | None = None) -> Result:
    # Q20: invoice-level VAT effect allocated to findings in line order (sequential, remainder last).
    pend.sort(key=lambda p: (p.finding.line is not None, p.finding.line or 0))
    state = {l.no: [l.amount, l.vat_rate] for l in inv.lines}
    prev = inv.vat_total
    held = any(p.finding.hold for p in pend)
    findings = []
    for p in pend:
        f = p.finding
        if p.fixed is not None:
            f.disputed_excl_vat, f.vat_effect, f.disputed_incl_vat = p.fixed
        elif not f.hold:
            # Q7 ruling (Kyle, 28 Oct): VAT charged too low is never a negative dispute. The finding stays
            # (verdict dispute, corrected invoice requested) at 0.00, and the gap is shown as information.
            # The line keeps its charged rate in the Q20 state, so on an invoice that also has other
            # findings their VAT effect is computed at the rate actually charged, the allocation still
            # telescopes to the invoice-level figure, and payable never rises above the invoice total.
            # No invoice in the 40 mixes an under-charge with other findings.
            under = f.line is not None and p.new_rate is not None and p.new_rate > state[f.line][1]
            if f.line is not None:
                state[f.line][0] -= p.delta
                if p.new_rate is not None and not under:
                    state[f.line][1] = p.new_rate
            new = vat_for(state)
            f.disputed_excl_vat, f.vat_effect = p.delta, prev - new
            f.disputed_incl_vat = p.delta + f.vat_effect
            prev = new
            if under:
                gap = vat_for({**state, f.line: [state[f.line][0], p.new_rate]}) - new
                f.issue += f" by {eur(gap)}"
                f.evidence += (f" VAT under-charged by EUR {eur(gap)}: information only, not paid on top and not"
                               f" disputed as a negative amount; corrected invoice requested (Q7).")
        f.small = is_small(f)
        f.provisional = held and not f.hold
        findings.append(f)
    tot_ex = sum((f.disputed_excl_vat for f in findings), D0)
    tot_vat = sum((f.vat_effect for f in findings), D0)
    tot_in = sum((f.disputed_incl_vat for f in findings), D0)
    money_found = any(abs(x) >= CENT for f in findings
                      for x in (f.disputed_excl_vat, f.vat_effect, f.disputed_incl_vat))
    # Q7: an under-charged VAT finding disputes the invoice (corrected invoice requested) at 0.00.
    verdict = "hold" if held else "dispute" if money_found or any(f.decision == "Q7" for f in findings) else "approve"
    rules = {f.rule for f in findings}
    if (verdict == "hold" or rules & ({"R13", "R10"} | BROKEN_TOTALS)
            or (verdict == "dispute" and tot_ex >= HIGH_LIMIT)):
        risk = "high"
    elif verdict == "dispute" or interp:
        risk = "medium"
    else:
        risk = "low"
    return Result(
        inv.id, inv.contractor, inv.number, inv.wo, verdict, risk, findings, sorted(interp, key=lambda q: int(q[1:])),
        notes, tot_ex, tot_vat, tot_in, D0 if held else inv.total - tot_in,
        add_working_days(inv.date, 10).isoformat() if verdict == "dispute" else None,
        readings=list(readings or []))


# ---------------------------------------------------------------- cross-invoice rules

def _net(orig: Invoice, credit: Invoice) -> tuple[Invoice | None, list[str]]:
    """R14, Q15: apply the credit note's lines to the original. Returns (netted invoice, problems)."""
    lines = {l.no: replace(l) for l in orig.lines}
    problems = []
    for c in credit.lines:
        match = next((l for l in lines.values() if l.unit_price == c.unit_price and norm(l.unit) == norm(c.unit)
                      and l.qty >= -c.qty), None)
        if match is None:
            problems.append(f"credit line '{c.raw}' matches no line on {orig.number}")
            continue
        if match.vat_rate != c.vat_rate:
            problems.append(f"credit line '{c.raw}' at {c.vat_rate}% VAT, original line {match.no} at {match.vat_rate}%")
        match.qty += c.qty
        match.amount += c.amount
    if problems:
        return None, problems
    blocks = {b.rate: replace(b) for b in orig.vat}
    for b in credit.vat:
        blocks.setdefault(b.rate, VatBlock(b.rate, D0, D0))
        blocks[b.rate].base += b.base
        blocks[b.rate].amount += b.amount
    netted = replace(orig, lines=[l for l in lines.values() if l.qty], vat=[b for b in blocks.values() if b.base],
                     subtotal=orig.subtotal + credit.subtotal, total=orig.total + credit.total)
    return netted, []


def _hist_number(row: dict) -> str:
    """Invoice number of a history row: the file id without its one-letter contractor prefix."""
    inv = row.get("invoice") or ""
    return inv.split("-", 1)[1] if re.match(r"^[a-z]-", inv) else inv


def _money(x) -> Decimal | None:
    try:
        return Decimal(str(x)) if x not in (None, "") else None
    except ArithmeticError:
        return None


def _match_credit(c: Invoice, row: dict, res: Result) -> Result:
    """A credit note against an earlier month's open dispute (history row with status letter_ready or waiting)."""
    orig, number = row["invoice"], _hist_number(row)
    disputed_in, disputed_ex = _money(row.get("amount_incl_vat")), _money(row.get("amount_excl_vat"))
    if disputed_in is not None:
        disputed, credit, basis, basis_en = disputed_in, -c.total, "incl. VAT", "including VAT"
    else:
        disputed, credit, basis, basis_en = disputed_ex or D0, -c.subtotal, "excl. VAT", "excluding VAT"
    res.linked_invoice = orig
    res.interpretations = sorted(set(res.interpretations) | {"Q15"}, key=lambda q: int(q[1:]))
    if credit == disputed:
        _note(res, f"Resolves the dispute of {orig}: credit EUR {eur(credit)} {basis} equals the disputed amount "
                   f"(Art. 4.8, Q15).",
              f"This credit note settles the dispute on invoice {number}: it matches the disputed EUR {eur(credit)} "
              f"{basis_en}.", "4.8b")
        res.link = {"invoice": orig, "kind": "credit_note", "match": "full", "remaining_incl_vat": D0,
                    "proposed_status": "credit received, matches"}
        res.risk = "medium" if res.risk == "low" else res.risk
    elif credit < disputed:
        rest = disputed - credit
        _note(res, f"Partly resolves the dispute of {orig}: credit EUR {eur(credit)} {basis}, disputed EUR "
                   f"{eur(disputed)}; EUR {eur(rest)} still open (Art. 4.8, Q15).",
              f"This credit note covers part of the dispute on invoice {number}: EUR {eur(rest)} {basis_en} is "
              f"still open, so that dispute stays open.", "4.8b")
        res.link = {"invoice": orig, "kind": "credit_note", "match": "partial", "remaining_incl_vat": rest,
                    "proposed_status": f"credit received, EUR {eur(rest)} still open"}
        res.risk = "medium" if res.risk == "low" else res.risk
    else:
        _note(res, f"Credit EUR {eur(credit)} {basis} is more than the EUR {eur(disputed)} disputed on {orig}; "
                   f"not resolved automatically (Art. 4.8, Q15).",
              f"This credit note is EUR {eur(credit - disputed)} more than we disputed on invoice {number}; "
              f"check with the contractor before booking it.", "4.8b")
        res.link = {"invoice": orig, "kind": "credit_note", "match": "over", "remaining_incl_vat": D0,
                    "proposed_status": None}
        res.risk = "high"
    return res


def check_all(invoices: list[Invoice], ctx: Context, history: list[dict] | None = None,
              confirmed=frozenset(), small_limit: Decimal = SMALL_LIMIT) -> list[Result]:
    """Check a batch. history: earlier invoices' decision state, one dict per invoice. Keys used: 'invoice',
    'wo', 'contractor', the optional 'meerwerk_excl_vat' (meerwerk billed on that invoice), and for open
    disputes 'status' (letter_ready, waiting, or resolved once Sanne confirmed it), 'amount_excl_vat', 'amount_incl_vat' (disputed) and
    'correction_requested' ('yes' when the dispute asked for a corrected invoice, Q7).
    confirmed: ids of invoices whose unknown work order Sanne confirmed (Art. 4.9 hold lifted).
    small_limit: a finding below this amount (excl. VAT, else incl.) is small; VAT-rate findings never are."""
    history = history or []
    by_number = {(i.contractor, i.number): i for i in invoices if not i.is_credit}
    netted: dict[str, Invoice] = {}
    credit_note: dict[str, tuple] = {}
    for c in (i for i in invoices if i.is_credit):
        orig = by_number.get((c.contractor, c.credit_ref))
        open_row = None
        if orig is None:  # an earlier month's open dispute; without one the credit note is held as before
            open_row = next((r for r in history if r.get("contractor") == c.contractor
                             and c.credit_ref in (r.get("invoice"), _hist_number(r))
                             and r.get("status") in LINKABLE), None)
        problems = [] if orig or open_row else [f"referenced invoice {c.credit_ref} not in this batch"]
        if orig and orig.wo != c.wo:
            problems.append(f"credit note is for {c.wo}, invoice {orig.number} for {orig.wo}")
        if open_row and open_row.get("wo") and open_row["wo"] != c.wo:
            problems.append(f"credit note is for {c.wo}, invoice {c.credit_ref} for {open_row['wo']}")
        if orig and not problems:
            n, problems = _net(netted.get(orig.id, orig), c)
            if n:
                netted[orig.id] = n
        credit_note[c.id] = (c, orig, problems, open_row)

    # DECIDE: a new invoice on the work order of an earlier invoice whose open dispute asked for a corrected
    # invoice (Q7, VAT charged too low) is read as that correction, not as a Q14 duplicate. It is checked
    # normally and linked to the original. Not covered by a Q decision; Kyle to confirm.
    replaces: dict[str, dict] = {}
    for inv in (i for i in invoices if not i.is_credit):
        row = next((r for r in history if r.get("wo") == inv.wo and r.get("contractor") == inv.contractor
                    and r.get("status") in LINKABLE and r.get("correction_requested") == "yes"
                    and r.get("invoice") not in (inv.id, inv.number)), None)
        if row:
            replaces[inv.id] = row

    def hist_for(inv):
        skip = replaces[inv.id]["invoice"] if inv.id in replaces else None
        return [r for r in history if r.get("wo") == inv.wo and r.get("invoice") not in (inv.id, inv.number, skip)]

    # R13, Q14: the earliest invoice per work order is checked; later ones (or any after history) are duplicates.
    first: dict[str, Invoice] = {}
    for inv in sorted((i for i in invoices if not i.is_credit), key=lambda i: (i.date, i.number)):
        first.setdefault(inv.wo, inv)

    results = {}
    for inv in invoices:
        if inv.is_credit:
            c, orig, problems, open_row = credit_note[inv.id]
            res = check_invoice(c, ctx, confirmed=c.id in confirmed)
            if problems:
                # DECIDE: an unverifiable credit note is not covered by Q15; held (closest: Q16).
                f = Finding(c.id, None, source_line(c, r"creditering|credit|factuur"), "R14", "Q15", "Credit note cannot be offset: " + "; ".join(problems),
                            ART["4.8b"], hold=True)
                res = _finish(c, [_Pending(f)], set(), [])
            elif open_row:
                res = _match_credit(c, open_row, res)
            else:
                res.interpretations = sorted(set(res.interpretations) | {"Q15"}, key=lambda q: int(q[1:]))
                res.risk = "medium" if res.risk == "low" else res.risk
                _note(res, f"Offset against invoice {orig.number} ({orig.id}) per Art. 4.8 (Q15).",
                      f"This credit note is offset against invoice {orig.number}.", "4.8b")
                res.linked_invoice = orig.id
            results[inv.id] = res
            continue
        earlier = hist_for(inv)
        dup_of = earlier[0].get("invoice") if earlier else (first[inv.wo].number if first[inv.wo] is not inv else None)
        target = netted.get(inv.id, inv)
        if dup_of:
            orig = by_number.get((inv.contractor, dup_of)) or next((i for i in invoices if i.id == dup_of), None)
            same = orig is not None and [(l.description, l.qty, l.amount) for l in orig.lines] == \
                [(l.description, l.qty, l.amount) for l in inv.lines] and orig.total == inv.total
            when = f" of {orig.date:%d-%m-%Y}" if orig else " (earlier month)"
            f = Finding(inv.id, None, wo_line(inv), "R13", "Q14", f"Work order {inv.wo} already invoiced on {dup_of}",
                        f"{ART['4.8a']} {inv.wo} already invoiced on invoice {dup_of}{when}"
                        + ("; same lines and same total." if same else "."))
            # Q14: the whole later invoice is disputed, net amount plus its full VAT; other checks would double count.
            res = _finish(target, [_Pending(f, fixed=(target.subtotal, target.vat_total, target.total))], set(), [])
        else:
            # Q10: meerwerk allowance is cumulative per work order across invoices.
            # DECIDE: under Q14 any second invoice on a WO is disputed whole, so prior meerwerk from history
            # only changes an outcome if Sanne overrules a duplicate; kept so the 250 stays per work order.
            prior = sum((Decimal(r.get("meerwerk_excl_vat") or 0) for r in earlier), D0)
            res = check_invoice(target, ctx, prior, confirmed=inv.id in confirmed)
            if target is not inv:
                before = check_invoice(inv, ctx, prior, confirmed=inv.id in confirmed)
                closed = [f for f in before.findings if (f.rule, f.line) not in {(g.rule, g.line) for g in res.findings}]
                for f in closed:
                    _note(res, f"{f.rule} on line {f.line} ({f.line_text}, {eur(f.disputed_excl_vat)} excl. VAT) "
                               f"is closed by the credit note (Art. 4.8, Q15).",
                          f"The problem on line {f.line} ({f.line_text}, EUR {eur(f.disputed_excl_vat)} excluding "
                          f"VAT) is settled by the credit note.", "4.8b")
                res.interpretations = sorted(set(res.interpretations) | {"Q15"}, key=lambda q: int(q[1:]))
                res.risk = "medium" if res.risk == "low" else res.risk
                res.payable_incl_vat = target.total - res.total_disputed_incl_vat if res.verdict != "hold" else D0
                res.linked_invoice = next(c.id for c, o, *_ in credit_note.values() if o is inv)
            row = replaces.get(inv.id)
            if row:
                res.linked_invoice = row["invoice"]
                res.link = {"invoice": row["invoice"], "kind": "corrected_invoice", "match": "replacement",
                            "remaining_incl_vat": D0, "proposed_status": "corrected invoice received"}
                _note(res, f"Corrected invoice for {row['invoice']} (same work order {inv.wo}); not a duplicate "
                           f"(Art. 4.8, Q7, Q14).",
                      f"This invoice replaces invoice {_hist_number(row)}, for which we asked a corrected invoice; it "
                      f"is checked as a new invoice, not as a duplicate.", "4.8a")
        results[inv.id] = res
    out = [results[i.id] for i in invoices]
    for f in (f for r in out for f in r.findings):
        f.small = is_small(f, small_limit)
    return out
