# Comparison with Sanne's verdicts (first 10 invoices)

Our verdicts agree with Sanne on 8 of 10 invoices, and the disputed amounts differ on 3. I checked both counts against `reference/sanne-verdicts.csv` and `tests/expected.json`. Sanne's notes are in Dutch; the translations are mine.

| Invoice | Sanne | Sanne amount | Ours | Our amount (excl. / incl. VAT) | Agree |
| --- | --- | --- | --- | --- | --- |
| h-2026-0031 | approve | 0.00 | approve | 0.00 / 0.00 | yes |
| w-DW26-004 | approve | 0.00 | approve | 0.00 / 0.00 | yes |
| j-F26-0007 | approve | 0.00 | approve | 0.00 / 0.00 | yes |
| h-2026-0038 | approve | 0.00 | dispute | 24.11 / 29.17 | no |
| b-B-26-0102 | dispute | 45.00 excl. | dispute | 46.44 / 56.19 | yes (amount differs) |
| w-DW26-009 | dispute | 385.00 excl. | approve | 0.00 / 0.00 | no |
| h-2026-0044 | dispute | 2 hours | dispute | 120.74 / 146.10 | yes |
| w-DW26-011 | dispute | VAT rate 21% should be 9% | dispute | 0.00 / 60.68 | yes |
| j-F26-0012 | approve | 0.00 | approve | 0.00 / 0.00 | yes |
| b-B-26-0097 | approve | 0.00 | approve | 0.00 / 0.00 | yes |

The three differences are the only ones. On h-2026-0044 and w-DW26-011 Sanne names the same finding and gives no euro figure, so there is nothing to differ on; we only add the amount (2 x 60.37 = 120.74, and 60.68 of VAT over-charged). The other five invoices are approved by both.

## h-2026-0038: she approved, we dispute 24.11 excl. / 29.17 incl. VAT

- Sanne: approve, "prijzen kloppen met de nieuwe prijslijst" (the prices match the new price list).
- Us: the prices do match the 2026 list, but the work was executed on 17-12-2025 and the invoice is dated 12-01-2026. The radiators were billed at 298.25 instead of 289.00 (18.50 over on 2 pieces) and the labour at 60.37 instead of 58.50 (5.61 over on 3 hours).
- Contract, Art. 4.2: "Bepalend is de datum van uitvoering van het werk, niet de factuurdatum. Werk uitgevoerd tot en met 31 december 2025 wordt gefactureerd tegen de prijzen van 2025." (The execution date decides, not the invoice date. Work up to and including 31 December 2025 is billed at 2025 prices.)
- Why: she looked at the invoice date, the contract looks at the execution date. The amount is small. The dashboard tags it Small, so Sanne can let it go with one click ("Approve: small amount") and the finding is still counted.

## b-B-26-0102: same verdict, 45.00 versus 46.44

- Sanne: dispute, "voorrijkosten op regulier werk, 45,00 + btw terugvragen" (call-out fee on regular work, reclaim 45.00 plus VAT).
- Us: dispute the call-out line as billed, 46.44 excl. VAT, 9.75 VAT, 56.19 incl.
- Contract, Art. 4.3: "Bij regulier werk zijn voorrijkosten in de prijzen inbegrepen." (On regular work the call-out fee is included in the prices.) Art. 4.2 sets the 2026 price: 45.00 x 1.032 = 46.44.
- Why: 45.00 is the 2025 price. The work was executed on 12-01-2026, so the 2026 indexed price is what was billed. Reclaiming 45.00 plus VAT (54.45) would leave 1.74 incl. VAT of an inadmissible charge unpaid back.

## w-DW26-009: she disputed, we approve

- Sanne: dispute, "meerwerk 385,00 boven de 250, geen akkoord gezien" (extra work of 385.00 above the 250, no approval seen).
- Us: approve. Work order WO-26-1006 records approval GA-0412 for 400.00 in the work order export, and the 385.00 is within it.
- Contract, Art. 4.5: "Boven dat bedrag is voorafgaand schriftelijk akkoord nodig, vastgelegd in de werkorder met een nummer GA-xxxx en een goedgekeurd bedrag." and "Met akkoord wordt ten hoogste het goedgekeurde bedrag vergoed." (Above that amount prior written approval is needed, recorded in the work order with a GA number and an approved amount. With approval, at most the approved amount is paid.)
- The same invoice has 9% VAT on stairwell painting labour, which I also checked. Art. 4.6 gives 9% on painting work (W01, W04 labour) on dwellings older than two years: "Op schilderwerk aan woningen die ouder zijn dan twee jaar geldt het verlaagde tarief van 9 procent, uitsluitend over de arbeid". I treat a stairwell as part of the dwelling (decision Q6), and the building dates from 1968, so 9% stands.
- Why: the approval is in the work order export, not on the invoice, which is easy to miss. 385.00 is below 400.00, so it is paid in full.

## Whole batch

Over all 40 invoices: 17 approve, 22 dispute, 1 hold. To dispute: EUR 2,649.85 excl. VAT and EUR 3,412.47 incl. VAT. These are the totals in `tests/expected.json`, which `tests/test_rules.py::test_totals` checks against the code (`rules.check_all`) on every run.

Incl. VAT is not simply excl. plus the VAT effect (2,649.85 + 662.62 = 3,312.47): h-2026-0052 has a total error of 100.00 on the invoice, which counts in the incl. VAT figure only.
