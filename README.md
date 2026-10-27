# Woonkring Oostervelde invoice check

A local MCP server and a Claude skill that check contractor invoices against Article 4 of the framework contract and prepare everything Sanne needs to decide.

## Project context

Woonkring Oostervelde is a housing association. Sanne in accounts payable checks the contractors' invoices by hand every month, and this project covers the 40 invoices of January. The tool applies Article 4 of the framework contract (prices, indexation, call-out fees, hours, extra work, VAT) with exact decimals, and the Claude skill drives it. Sanne decides everything in a local dashboard in the browser. Nothing is sent or paid automatically: the tool only proposes verdicts and drafts Dutch letters.

## Getting started

### a) Claude Desktop (Cowork)

1. Install uv once. Windows PowerShell: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`. macOS or Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh` (see docs.astral.sh/uv).
2. In Claude Desktop open Cowork, then Customize, then Plugins, and add the marketplace `laughable-9/oostervelde-invoice-check`.
3. Install the plugin `invoice-check`.
4. Start a Cowork task and say "check the January invoices".

Requirements: a paid plan with code execution turned on. Local MCP servers work only in Cowork or Claude Code, not in normal chat.

### b) Claude Code

```
claude plugin marketplace add laughable-9/oostervelde-invoice-check
claude plugin install invoice-check@oostervelde
```

Or, from a clone of this repo: `claude --plugin-dir .`. Then ask it to check the January invoices.

### c) Tests only

```
uv run --extra dev pytest
```

## What you get

- A review list, `output/<run>/review-list.md`, with every invoice, its proposed verdict and the evidence.
- Draft letters in Dutch for the disputed invoices, in the same run folder.
- A dashboard (`review.html`) that opens in the browser, where Sanne approves, disputes or holds each invoice.
- `decisions.csv`, an append-only log of her decisions.

## Project structure

```
server.py            MCP server: tools, review list, letters, decisions log
dashboard.py         local dashboard server that Sanne uses
report.py            builds the review.html page
rules.py             the Article 4 checks, all amounts in exact decimals
parsers.py           reads the invoice, work order and price files
skills/invoice-check/SKILL.md   the Claude skill: how to run the check
.claude-plugin/      plugin.json and marketplace.json
.mcp.json            starts the MCP server through uv
pyproject.toml       dependencies (mcp; dev extra: pytest), uv.lock pins them
tests/               pytest suite and expected.json (our verdicts and amounts)
invoices/            the 40 January invoices (text)
work-orders-export.csv, price-agreement-2025.csv, contract-excerpt.md   input data
reference/           Sanne's verdicts on the first 10 invoices
output/              generated runs and comparison.md
NOTES.md             how I read the contract, decisions and open points
```

## Results

Over all 40 invoices: 17 approve, 22 dispute, 1 hold. To dispute: EUR 2,649.85 excl. VAT and EUR 3,412.47 incl. VAT. On the 10 invoices Sanne checked, we agree on 8 verdicts. See [output/comparison.md](output/comparison.md) for the differences and [NOTES.md](NOTES.md) for the decisions.
