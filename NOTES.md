# NOTES

This file records how I read the contract, what I decided, and where the human stays in charge. The reference for every check is Article 4 of the framework contract (Dutch original), not what anyone believes it says. The design rule is that every amount is computed with exact decimals, never by the model and never with floating point. That is now in code (`rules.py`), and I checked the 10 reference invoices by hand first with a throwaway Python Decimal script. The tool is built: an MCP server, a skill, a local dashboard and Dutch draft letters. Sanne makes every final decision; the tool only prepares findings and drafts. EUR figures in this file use a dot (24.11); the Dutch quotes keep the Dutch comma.

## Decisions and translations

### Translations I relied on

Condensed from my full table in `notes/rulebook.md`. I read the original Dutch. The Dutch column is quoted from the contract, with "..." where I left words out. The translations are mine, with no sworn or native review; the Dutch is the reference.

| Art. | Dutch key phrase | English |
| --- | --- | --- |
| 4.1 | De eenheid in de prijslijst is leidend ... mag deze niet hoger uitkomen | The unit in the price list is leading; the converted price may not come out higher |
| 4.2 | eenmalig geïndexeerd met 3,2 procent, afgerond op hele centen per eenheid | indexed once by 3.2 percent, rounded to whole cents per unit |
| 4.2 | Bepalend is de datum van uitvoering van het werk, niet de factuurdatum | The execution date decides, not the invoice date |
| 4.2 | Werk uitgevoerd tot en met 31 december 2025 wordt gefactureerd tegen de prijzen van 2025 | Work up to and including 31 Dec 2025 is billed at 2025 prices |
| 4.3 | alleen vergoed bij werkorders van het type spoed, en ten hoogste één keer per werkorder | Call-out costs only on emergency orders, at most once per work order |
| 4.3 | Bij regulier werk zijn voorrijkosten in de prijzen inbegrepen | On regular work, call-out is included in the prices |
| 4.4 | Uren daarboven worden alleen vergoed als Woonkring Oostervelde vooraf extra uren heeft goedgekeurd | Maximum labour hours per work order; extra hours only if approved in advance, recorded in the work order (MU-xxxx) |
| 4.5 | Meerwerk tot en met EUR 250,00 exclusief btw per werkorder mag zonder voorafgaand akkoord worden uitgevoerd | Meerwerk up to and including EUR 250.00 excl. VAT per work order may be done without prior approval |
| 4.5 | ook niet het deel tot EUR 250,00 | Without approval above 250, nothing is paid, not even the first 250 |
| 4.5 | Met akkoord wordt ten hoogste het goedgekeurde bedrag vergoed | With approval (GA-xxxx), at most the approved amount |
| 4.6 | Op schilderwerk aan woningen die ouder zijn dan twee jaar geldt het verlaagde tarief van 9 procent, uitsluitend over de arbeid (prijslijstcodes W01 en W04) | 9% only on labour (W01, W04) of painting work on dwellings older than two years; 21% on material and everything else |
| 4.7 | niet in de prijslijst staan en niet als meerwerk zijn vermeld | Not in the price list and not stated as meerwerk: only paid after prior approval |
| 4.8 | Elke werkorder wordt één keer gefactureerd. Correcties lopen via een creditfactuur | Each work order is invoiced once; corrections via a credit invoice |
| 4.9 | Een factuur zonder geldige werkorder ... wordt niet betaald tot de opdracht is bevestigd | No valid work order: not paid until the assignment is confirmed |
| 4.10 | Betwiste facturen of factuurregels worden binnen 10 werkdagen schriftelijk en met reden aan de opdrachtnemer gemeld. Het onbetwiste deel wordt wel betaald | Disputes are reported to the contractor in writing, with a reason, within 10 working days; the undisputed part is paid (payment within 30 days of receipt) |

Glossary of the invoice terms that matter most:

- werkorder: work order
- uitvoeringsdatum: execution date
- voorrijkosten: call-out fee
- spoed / regulier: emergency / regular (the two work order types)
- arbeid: labour
- meerwerk: extra work outside the work order

The full glossary is in `notes/rulebook.md`.

### Interpretation decisions

Q1 to Q20 were decided on 27 Oct 2026, all option A (my recommended option). Full options and consequences are in `notes/rulebook.md`. The six with the most money or risk are Q2, Q7, Q9, Q15, Q17 and Q20; the rest are small. Q21 was added overnight and is only proposed.

| # | Question | Decision | Why |
| --- | --- | --- | --- |
| Q1 | Rounding of the 3.2% indexation | Half-up per unit, before multiplying by quantity | Standard Dutch commercial rounding; half-even gives identical prices here |
| Q2 | Work done Dec 2025, invoiced Jan 2026 | Execution date decides the price year | Art. 4.2 says so outright |
| Q3 | Copper pipe billed per m, listed per 25 m roll | Convert 167.70 / 25 with no intermediate rounding (disputed 21.68 on h-2026-0057) | 4.2 rounds per list unit; 4.1 adds no second rounding |
| Q4 | Price below list price | Not flagged | Nothing in Art. 4 forbids a lower price |
| Q5 | "Older than two years" | Execution year minus build year: 3 or more is older, 1 or less is not, exactly 2 goes to hold and ask | Execution date is the reference the contract uses in 4.2; no guessing |
| Q6 | Stairwell as "woningen" | Counts as a dwelling, so 9% on labour stands (DW26-009) | Contract does not exclude common parts |
| Q7 | VAT charged too low | Dispute: 0.00 excl. VAT, negative VAT effect, ask for corrected invoice. Addition 28 Oct: I ruled that these findings dispute 0.00 incl. VAT, never a negative amount, so payable never goes above the invoice total; I still ask for a corrected invoice and show the VAT gap as information only. | 4.6 binds in both directions |
| Q8 | VAT method | Per rate base, half-up; VAT effect = invoiced VAT minus VAT on the corrected base | All 40 invoices match this exactly |
| Q9 | Meerwerk above GA amount | The approved amount caps all meerwerk (640 vs GA 400: dispute 240.00). Rejected reading: 250 free + 400 approved = 650 | "Ten hoogste het goedgekeurde bedrag" is a ceiling; the 250 only applies without approval |
| Q10 | Scope of the 250 | Cumulative per work order across invoices | Text says "per werkorder"; per line would allow splitting |
| Q11 | Fixed-rate items and hour maximum | Only labour lines (H02, W01, B01, J01) count as hours | The contract counts "arbeidsuren" only |
| Q12 | Partial MU approval | Dispute only hours above max plus approved hours | Nothing says the approval lapses when exceeded |
| Q13 | Price for excess hours | Allowed hours times list price; split price and hours findings | Same total, cleaner by rule |
| Q14 | Duplicate invoice | Dispute the whole later invoice | Breach is clear from the data; hold is for 4.9 |
| Q15 | Credit note and original | Net the credit first; original approved if nothing remains. The review list still shows the closed finding and the credit that settled it, and it counts toward the contractor pattern | 4.8 says the client offsets; avoids recovering 46.44 twice |
| Q16 | Unknown work order | Hold the whole invoice; other checks still run, shown as provisional | 4.9 is a suspension, not a rejection |
| Q17 | Off-list item without meerwerk label | Dispute the line ("no prior approval found; send it if you have one") | The rest of the invoice can still be paid under 4.10 |
| Q18 | Error in invoice total only | Dispute; reported as an incl. VAT difference (100.00), 0.00 excl. VAT | The error is in the total, not a priced line |
| Q19 | Sub-cent differences | Exact to the cent, no tolerance | Sanne has to quote exact amounts to a contractor, and per rate base leaves no rounding noise |
| Q20 | Per-finding VAT when an invoice has several findings | Compute the VAT effect once per invoice and allocate it to findings in line order; the last finding takes the remainder | Findings in the dispute letter always add up to the invoice-level figure; separate rounding created a phantom cent on h-2026-0038 (5.07 vs 5.06). The invoice itself is never changed. |
| Q21 | Dispute deadline (Art. 4.10) | Proposed, to confirm: show a "dispute by" date of invoice date + 10 working days (Mon-Fri, Dutch public holidays not modelled), labelled as a proxy | The contract gives 10 working days but not the start; the receipt date is not in the data |

These decisions are my readings of the contract. Woonkring and MSTR have not confirmed them. In a real engagement I would confirm the open readings with Sanne before relying on them.

### Where I disagree with Sanne's beliefs about the contract

Where her statement and the contract differ, I follow the contract. Her statements are context, not authority. Her reference set is only 10 invoices, so where I name other invoices below I mean her stated method would miss the error, not that she did.

| Sanne says | Contract says | Effect |
| --- | --- | --- |
| "invoices from January use the new prices" | 4.2: execution date decides | She approved h-2026-0038 (executed 17 Dec 2025) at 2026 prices: 24.11 over-billed. The same error is present on h-2026-0040 and B-26-0089; her method would miss both |
| Painter VAT: "I usually just check that the painter has two VAT lines" | 4.6: 9% only on W01 and W04, only on dwellings older than two years | DW26-015 (new build) has two lines but is wrong; h-2026-0061 (plumber at 9%) is wrong; DW26-002 has one line but labour should be 9% |
| Voorrijkosten "They're only allowed on emergency jobs" | 4.3: also at most once per work order | Right rule, but with her method h-2026-0058 (two call-outs) would be missed. Her B-26-0102 note says "45,00 + btw terugvragen"; 46.44 was billed |
| Small excess hours: "If the amount is small I let it go" | 4.4: no minimum | Every excess hour is a finding |
| Meerwerk without approval: "I think if they don't have it, we only pay the 250? I'd have to check the contract." (unsure) | 4.5: nothing is paid, not even the first 250 | F26-0024: dispute 310.00, not 60.00 |
| DW26-009 note: "meerwerk 385,00 boven de 250, geen akkoord gezien" | 4.5: WO-26-1006 has GA-0412 for 400 | Her dispute looks wrong; 385 is covered |
| Credit notes: "Then I just net them out" | 4.8: same | Correct |
| Unknown work order: "it goes on hold until the housing officer confirms the job" | 4.9: same | Correct (DW26-013) |
| "I don't compare them to each other" | 4.8: one invoice per work order | A duplicate such as F26-0019 would be missed |
| "I take every line and look it up in the price list" | 4.1 unit conversion; 4.7 off-list approval | A plain lookup would miss h-2026-0057 and B-26-0140 |

## Where Sanne decides

This section describes what is built and running now. Sanne signs off on every payment and said "I'm not going to approve forty invoices on a computer's word". So the solution never decides. It calculates, proposes and explains, and she decides every invoice. Below, the four questions from the brief, each answered.

**Which calls can your solution make on its own, and which should always go to Sanne?**

On its own (no judgment, all deterministic code):

- reading and parsing invoices
- looking up prices, work orders and approvals
- all arithmetic, with exact decimals
- applying the rulebook with my decisions
- proposing a verdict (approve, dispute or hold) per invoice, and one suggested next step
- assigning a risk level
- matching a credit note or a corrected invoice to an earlier dispute and flagging it
- drafting the review list and the dispute letters

Always Sanne: the final verdict on every invoice, including clean ones. I considered bulk-approving clean invoices and rejected it. A faulty invoice could land in the clean group, most likely through an interpretation the contract does not settle rather than through arithmetic. Instead every invoice has a risk level and the review list is sorted by it:

- High: hold (unknown work order), duplicate invoice, totals that do not add up, wrong VAT rate, a dispute of EUR 100.00 or more excl. VAT, or EUR 100.00 or more incl. VAT for a total error.
- Medium: any other dispute, or a clean invoice whose outcome depends on one of my interpretation decisions (for example w-DW26-009 is clean only because I read a stairwell as part of a home, Q6).
- Low: zero findings, every line exactly at list price, no interpretation involved.

Risk levels are set by fixed rules, not by Claude's judgment. Also always hers: closing a dispute (a credit note that the tool matched is only flagged, she confirms), letting a small amount go, rejecting an invoice, and sending any letter.

**What does she see when your solution isn't sure, and how does she say yes, no or change this?**

She decides in a local dashboard, `review.html`. The MCP server serves it on 127.0.0.1 only, with a random token per session and Host and Origin checks on every request, and it opens in her browser automatically after the check. She can also decide in the Claude chat. Both routes use the same `record_decision` code and the same `decisions.csv`, which is append-only: the latest row for an invoice wins, and Undo adds a row instead of deleting one. If she opens `review.html` as a plain file, without the server, it is a read-only snapshot with no buttons.

There are three kinds of unsure. First, missing information that blocks a check (an unknown work order, or a building exactly two years old, Q5): the tool cannot check, so the invoice is proposed as hold, with the reason, the evidence and the options (for example "work order WO-26-1099 not found; confirm the job with the housing officer"). Second, where the contract puts the burden on the contractor (an off-list item with no recorded approval, Q17): the tool proposes dispute and invites the contractor to show the approval ("no approval found, send it if you have one"). Third, the answer depends on a reading of the contract: the verdict is proposed as normal, but the invoice is marked medium risk and names the decision (for example Q6). Every finding shows the invoice line, the contract article in plain words, the amounts excl. and incl. VAT, and the data it relied on, so she can check it without opening anything else. Each dispute also shows a "dispute by" date: invoice date + 10 working days (Mon-Fri, Dutch public holidays not modelled), labelled as a conservative proxy because Art. 4.10 does not say when the 10 days start and the receipt date is not in the data (Q21, proposed). Disputes close to that date sort to the top. Credit notes and corrected invoices that relate to an earlier dispute appear under Needs attention.

Each invoice shows one suggested next step as the main button. The rest sit under More options. The actions, in her workflow words:

- Approve for payment.
- Prepare dispute letter, then Mark letter as sent, then Waiting for contractor, then Close dispute with one of four outcomes: credit note received, corrected invoice received, contractor was right, withdrawn.
- Put on hold, and Ask housing officer to confirm; then Work order confirmed once the job is confirmed.
- Reject invoice, with preset reasons or her own.
- Change outcome. It requires a reason and counts as an overrule.
- Approve: small amount (let it go).
- Undo.

Small and repeat. A finding under the small threshold (default EUR 25.00 excl. VAT) is tagged Small. The tag is per finding, not per invoice. For example the two findings on h-2026-0038 (18.50 and 5.61) are each Small, even though together they are a systematic error. The tag only offers; letting go stays Sanne's explicit, logged choice. Every let-go is logged per contractor and rule across months. When the same contractor and rule reach the repeat count (default 3), the finding is no longer Small and needs a reason. VAT-rate errors are never Small, because the invoice must be legally correct. Both numbers are in Settings and stored in `settings.json` in her folder. Changing them relabels findings but never changes an amount.

Disputes across months. If a credit note refers to an invoice with a dispute that is waiting, the tool matches it as full, partial or mismatch and flags it under Needs attention; she confirms before anything closes. A corrected invoice on the same work order as a dispute that asked for a correction is read as a replacement and not as a duplicate (Kyle confirmed this reading), and the card shows the previous version. A resend of an old invoice with a new number in a later month is still caught as a duplicate.

**Can anything reach a contractor without her approval?**

No. There is no send tool at all: the MCP server has no sending capability, and the skill tells Claude never to send or claim to have sent anything. The server can read the dataset and write its own output files; it cannot contact anyone. If Sanne's Claude has other connectors such as email, sending remains her own action and the skill never triggers it (see the last section for the honest limit of that).

Letters are plain Dutch .txt files, one per contractor, with the status in the file name: `.CONCEPT.txt` until she agrees, and the ready name only after she has decided. They contain a small table with the invoice data, the contract text quoted verbatim (a test checks every quote against the contract), and an overview with the invoice amount, the disputed amount and what we pay now. An English translation is shown in the dashboard. The letters carry no internal rule codes. She can edit and send a letter herself; she should never need to fix its layout.

**When she overrules your solution, what happens with that?**

Her decision always wins and is never silently re-flagged. A reason is required and is saved in `decisions.csv`. Overrules are counted per contractor and per rule. If she overrules the same rule three or more times, the review list says so, because either my rule is wrong and should be revisited, or a contractor pattern is being let through. Changing an outcome counts as an overrule, and a changed amount replaces my proposal everywhere, including the letter and its overview. Small amounts she lets go are counted the same way, for example (made-up figures) "Hoekstra: 4 small overcharges let go in the last 3 months, EUR 87.40 in total". A decision made in the dashboard survives a restart of the server.

**Supporting pieces**

- Install: the repo is a Claude plugin (skill plus MCP server) that she installs from GitHub in Cowork or Claude Code. uv must be installed once. If uv is missing the server cannot start, so the skill now detects the missing server and walks her through installing uv; it is the one thing a company rollout would need IT to preinstall.
- The review list is in English for reviewers, with Dutch terms in brackets.
- Tests: 96 pass at the moment (`pytest -q`). The flaky dashboard test was caused by the server rejecting a request without reading its body, which resets the connection on Windows; it now reads the body first, and the suite passed three full runs in a row (96 tests).

## What changed along the way

- 27 Oct 2026: I read the brief late because the brief link was broken at first. I used the waiting time to translate Article 4 and profile the data.
- 27 Oct 2026: My first translation of the invoices was made by a regex and vocabulary script, and I had spot-checked only 6 of the 40. That is not enough for a contract-based check, so I had every translation re-read against the original.
- 27 Oct 2026: I chose to write a rule book from Article 4 before any code, because every finding must be defensible line by line and to the cent.
- 27 Oct 2026: I found that VAT on all 40 invoices is computed per rate base with half-up rounding. I considered computing VAT per line and rejected it: it would create 7 false 1-cent findings. So I compute per rate base (Q8).
- 27 Oct 2026: Two of Sanne's 10 reference verdicts look wrong against the contract. h-2026-0038 should be a dispute (executed Dec 2025 but billed at 2026 prices). w-DW26-009 is fine, because GA-0412 covers the 385.00 meerwerk. Her note on b-B-26-0102 reclaims "45,00 + btw" while 46.44 was billed. The hand-check below confirmed this.
- 27 Oct 2026: I found hidden arithmetic errors. h-2026-0052 total is 100.00 too high; w-DW26-016 has a line of 232.90 that should be 222.90.
- 27 Oct 2026: Meerwerk with approval: I considered stacking the free 250 on top of the approved 400 (650) and rejected it, because 4.5 caps what is paid at the approved amount (Q9).
- 27 Oct 2026: Added a cross-month duplicate check to the design. Sanne's real failure was a resend "a month later with a new number", which a single-month batch cannot catch. Decided on a CSV ledger (one row per invoice, written only after Sanne signs off) checked by work order and by fingerprint (supplier, address, execution date, amount). About 40 invoices a month for a 7-year retention period (my assumption for the Dutch accounting rule, to be confirmed) is roughly 3,400 rows, so CSV is enough and Sanne can open it in Excel.
- 27 Oct 2026: Chose a public GitHub repo for submission so the commit history shows how the work developed; the data is fictional.
- 27 Oct 2026: Hand-check of Sanne's 10 invoices, to the cent, including qty x price on all 26 item lines. I agree with Sanne on 8 of 10 verdicts. Two verdicts differ: h-2026-0038 (she approved; work executed 17-12-2025 so 2025 prices apply, dispute 24.11 excl. VAT) and w-DW26-009 (she disputed; GA-0412 approves 400.00 which covers the 385.00 meerwerk, so approve). On a third, b-B-26-0102, the verdict is the same but the amount differs (46.44 was billed, not 45.00, so 56.19 incl. VAT). Found that per-finding VAT rounding can create a phantom cent (my first split gave 3.89 + 1.18 = 5.07, which did not add up to the invoice figure 5.06), decided Q20.
- 27 Oct 2026: My own rulebook quick scan was wrong. I had written that VAT effects agree under the per-rate-base and per-line methods except on h-2026-0058. The hand-check showed h-2026-0038 also differs (5.06 against 5.07). I fixed the scan figures and added Q20. Lesson: quick-scan numbers are not trusted until hand-checked, and the quick-scan money figures for the other 30 invoices are still unverified.
- 27 Oct 2026: Designed how Sanne stays in charge. I considered bulk approval of clean invoices and rejected it in favour of risk levels (high, medium, low) with Sanne confirming every invoice. Clean invoices that depend on an interpretation decision are medium, not low. Added record_decision as the only tool that records decisions, decisions.csv for persistence, DRAFT/READY letter states, a EUR 25 "small" tag with logging, and overrule counting per contractor and rule.
- 28 Oct 2026 (overnight): Independent review of these notes and the hand-check. I had counted agreement with Sanne as 7 of 10; the review corrected it to 8 of 10. I also made this file honest about what is built (nothing yet), restored exact quotes, and added the dispute deadline proposal (Q21).

- 28 Oct 2026: Claude's first proposal for setup was to edit Claude Desktop's config file by hand: paste a JSON block and set the path to the data folder. I overruled that for ease of installation. Sanne should not have to edit JSON. She should be able to point Claude at the GitHub repo and install it from there. What we did instead: the repo is also a Claude plugin, with a marketplace and a plugin manifest. In Claude Desktop she opens Cowork, then Customize > Plugins, adds the repo as a marketplace and installs the plugin. That brings in both the skill and the MCP server. This has costs:
  - It needs a paid Claude plan and code execution switched on.
  - uv must be installed once.
  - Local MCP servers do not load in normal Desktop chat, only in Cowork and Claude Code, so she works in Cowork.
  The plugin is built; the Windows install test is still open (see the last section).
- 28 Oct 2026: Decisions first went only through the chat: Sanne told Claude approve, dispute or hold and Claude called `record_decision`. Kyle found that unintuitive, so I chose buttons on the dashboard instead. The MCP server also serves the dashboard on localhost (127.0.0.1 only, a random token per session), and the buttons write through the same `record_decision` code and the same `decisions.csv` as the chat, with the same overrule counting. Changing a proposal needs a reason and counts as an overrule; Undo adds a row that reopens the invoice and deletes nothing. The file snapshot of the page stays read-only. Nothing in this can send email or pay.
- 28 Oct 2026: Kyle ruled on Q7 (under-charged VAT). I had proposed a negative VAT effect on the dispute. He decided that these findings dispute 0.00 incl. VAT, never a negative amount, and that we still ask for a corrected invoice. The reason: what we pay must never go above the invoice total. A test now checks that.
- 28 Oct 2026: Kyle wanted the review list as one dashboard instead of a spreadsheet. I had produced a CSV review list. He called it "a jumbled mess" for Sanne, so `review.html` became the main view and the Markdown review list stays as a record.
- 28 Oct 2026: Kyle did not like the first button labels. My first version felt like a checklist with vague labels. He asked for her workflow words instead (Prepare dispute letter, Mark letter as sent, Waiting for contractor, Close dispute), one suggested next step per invoice, and the rest under More options.
- 28 Oct 2026: Kyle decided against a special button for an unknown work order. I had suggested one. We built a general Reject invoice with preset reasons or her own. The reason: neither Sanne nor the contract documents a rejection for this case, only the hold, so a dedicated button would invent a rule.
- 28 Oct 2026: Kyle asked for the letters to be reformatted so that she never edits them. My first letters had raw invoice lines with column bars and mixed languages. They are now plain Dutch with a small table, verbatim contract quotes, an overview of the amounts, and the status in the file name.
- 28 Oct 2026: Kyle asked for the work order to be shown on each invoice, plus sorting and filtering. The reason: Sanne said the work order export "is a nightmare" and she doesn't always open it, so the facts a finding relies on (maximum hours, approvals, job type) now sit on the invoice itself. Sorting and filtering replaced a row of status pills that I found messy.
- 28 Oct 2026: Kyle confirmed that a corrected invoice on the same work order as a dispute that asked for a correction is a replacement, not a duplicate. I had treated every second invoice on a work order as a duplicate (Art. 4.8), which would flag a contractor for doing what we asked.
- 28 Oct 2026: Two findings from my own checks. First, 18 of 53 contract quotes were not verbatim, so I fixed them and added a test that checks every quote against the contract. Second, an independent blind hand-check of all 30 other invoices matched the code on all fields. That closes the open point about the 30 unverified invoices, but it is still my reading of the contract.

## What isn't finished

Built and tested: the MCP server, skill, dashboard, decisions log, letters, cross-month matching and the run over all 40 invoices (17 approve, 22 dispute, 1 hold). The comparison with Sanne's 10 verdicts is in `output/comparison.md`. Not finished or not certain:

- The plugin install in Cowork has not been tested on Windows yet. Kyle tests it before submitting. [Placeholder for Kyle to update: result of the Windows Cowork install test, date and what happened.]
- The file lock for two Cowork sessions writing at once is tested in one process only, not with two real sessions.
- An invoice number reused in a later month shares one decision state, so the second invoice would show the earlier decision.
- The MCP SDK is pinned below version 2. A newer major version may need changes.
- Public holidays are not in the dispute-by date (Q21), so the date can be a day or more early. That is the safe side, and it is labelled as an estimate. Q21 itself is still my proposal.
- A new contractor layout needs a new parser. An invoice in an unknown layout is put on hold with an error; the tool never guesses.
- Hover help does not exist on phones. Tapping works.
- Things Sanne should confirm with the contract owner, because they move money or a contractor could challenge them: Q7 (under-charged VAT), Q9 (cap at the approved amount), Q10 (cumulative 250), Q15 (credit netting) and Q17 (off-list line). If she disagrees, the decision is reopened; the code reads the decisions from one rules config.
- All decisions are my reading of the contract. None is confirmed by Woonkring, MSTR, Sanne or a lawyer, and my translations have no sworn or native review.
- Art. 4.7 approvals cannot be verified, because the work order export has no field for them. An off-list line is flagged as "no approval found", not "no approval exists".
- "Older than two years" (Art. 4.6) is approximated from the build year only, since the work order gives no completion date.
- Another connector in the same Claude session (for example email) could send mail. The skill tells Claude never to send, but that is an instruction, not a technical block. For deployment I would run it in a Claude project with no mail connector, and the letter is a file that only Sanne sends.
- Only the 10 reference invoices have expected values in `tests/expected.json`. The other 30 were hand-checked blind, but that check is not a test in the repo.
- Not done yet: the video.
