"""Render review.html, the one-file offline dashboard for Sanne. Stdlib only, no external requests.

Python builds one JSON data block (every string from an invoice lives in it, "<" escaped as \\u003c);
the page script builds the DOM with textContent only and composes the Dutch letters from structured parts.
"""
import json
import re
from decimal import Decimal, InvalidOperation
from html import escape

RISKS = ("high", "medium", "low")
VERDICTS = ("hold", "dispute", "approve")
# Letter wording as written by server.letter(); the page lets Sanne change these for every letter.
GREETING = "Geachte heer, mevrouw,"
CLOSING = "Met vriendelijke groet,"
DEFAULTS = {"greeting": GREETING, "closing": CLOSING, "signer": "",
            "dept": "Woonkring Oostervelde, crediteurenadministratie", "num": "nl"}

# Lucide 0.460.0 icons, path data verbatim (viewBox 24, stroke 2, currentColor).
ICONS = {
    "chevron-left": '<path d="m15 18-6-6 6-6"/>',
    "chevron-right": '<path d="m9 18 6-6-6-6"/>',
    "chevron-down": '<path d="m6 9 6 6 6-6"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "settings-2": '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
    "copy": '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>'
            '<path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>'
                '<line x1="12" x2="12" y1="15" y2="3"/>',
    "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "chevrons-up-down": '<path d="m7 15 5 5 5-5"/><path d="m7 9 5-5 5 5"/>',
    "chevrons-down-up": '<path d="m7 20 5-5 5 5"/><path d="m7 4 5 5 5-5"/>',
    "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "sliders-horizontal": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/>'
                          '<line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/>'
                          '<line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/>'
                          '<line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/>'
                          '<line x1="16" x2="16" y1="18" y2="22"/>',
}

CSS = """
:root{color-scheme:light dark;
--bg:#e9edf0;--surface:#fff;--surface2:#f4f6f8;--ink:#14212b;--mute:#566470;--line:#d3dae0;--line2:#b6c1c9;
--accent:#0f6b73;--accent-ink:#fff;--accent-bg:#d9eeef;--quote:#f0f3f5;
--high:#c2410c;--high-bg:#fde6d8;--medium:#946200;--medium-bg:#f8ebbd;--low:#5a6b77;--low-bg:#e3e9ed;
--approve:#1c7443;--approve-bg:#dbf0e3;--dispute:#b42318;--dispute-bg:#fbe1de;--hold:#3552a3;--hold-bg:#e0e6f6;
--sans:"Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
--serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
--mono:ui-monospace,"Cascadia Mono","SF Mono",Consolas,monospace}
@media (prefers-color-scheme:dark){:root{
--bg:#0e161c;--surface:#16212a;--surface2:#1b2832;--ink:#e2e9ee;--mute:#92a2ae;--line:#2a3a46;--line2:#40525f;
--accent:#5cc2c9;--accent-ink:#06282b;--accent-bg:#14363a;--quote:#1c2a34;
--high:#f59a6b;--high-bg:#402516;--medium:#e5bd5c;--medium-bg:#3b3010;--low:#9fb0bb;--low-bg:#25323b;
--approve:#6fcf97;--approve-bg:#173a2a;--dispute:#f4938a;--dispute-bg:#452220;--hold:#93abf2;--hold-bg:#1f2b4f}}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);font-variant-numeric:tabular-nums}
button,input,select,textarea{font:inherit;color:inherit}
button{cursor:pointer}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
svg.i{width:1.1em;height:1.1em;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
.app{display:grid;grid-template-rows:auto 1fr;height:100vh}
.top{background:var(--surface);border-bottom:1px solid var(--line);padding:.75rem 1.25rem}
.top-row{display:flex;align-items:center;gap:.75rem;flex-wrap:wrap}
.top h1{font-size:1.15rem;margin:0;font-weight:650;letter-spacing:-.01em}
.run{color:var(--mute);font-size:.85rem}
.sp{flex:1}
.chip{display:inline-flex;align-items:center;gap:.35rem;padding:.1rem .6rem;border-radius:999px;font-size:.8rem;font-weight:600;
background:var(--low-bg);color:var(--low)}
.btn{display:inline-flex;align-items:center;gap:.4rem;padding:.4rem .75rem;border:1px solid var(--line2);background:var(--surface);
border-radius:6px;font-weight:550}
.btn:hover{background:var(--surface2)}
.btn.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.btn.primary:hover{background:var(--accent);filter:brightness(1.1)}
a.btn{text-decoration:none;color:var(--ink)}
.btn.icon{padding:.4rem}
.btn[disabled]{opacity:.4;cursor:default}
.kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:.75rem;margin-top:.75rem}
.kpi{background:var(--surface2);border:1px solid var(--line);border-radius:8px;padding:.55rem .8rem;min-width:0}
.kpi .l{font-size:.75rem;color:var(--mute);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.kpi .v{font-size:1.35rem;font-weight:650;letter-spacing:-.01em;white-space:nowrap}
.kpi .v small{font-size:.9rem;color:var(--mute);font-weight:500}
.bar{height:6px;border-radius:3px;background:var(--line);margin-top:.35rem;overflow:hidden}
.bar i{display:block;height:100%;background:var(--approve)}
.panes{display:grid;grid-template-columns:minmax(320px,420px) 1fr;min-height:0}
.queue{display:flex;flex-direction:column;min-height:0;background:var(--surface);border-right:1px solid var(--line)}
.q-head{position:relative;padding:.75rem;border-bottom:1px solid var(--line)}
.search{display:flex;align-items:center;gap:.5rem;border:1px solid var(--line2);border-radius:6px;padding:0 .6rem;background:var(--surface2)}
.search input{flex:1;min-width:0;border:0;background:transparent;padding:.45rem 0;outline:0}
.search:focus-within{outline:2px solid var(--accent);outline-offset:2px}
.tabs{display:flex;flex-wrap:nowrap;gap:2px;margin-top:.6rem;padding:2px;overflow-x:auto;scrollbar-width:none;background:var(--surface2);
border:1px solid var(--line);border-radius:8px}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;display:inline-flex;align-items:center;gap:.25rem;border:0;background:transparent;border-radius:6px;white-space:nowrap;
padding:.25rem .4rem;font-size:.8rem;font-weight:550;color:var(--mute)}
.tab:hover{color:var(--ink)}
.tab b{font-weight:600;font-size:.72rem;color:var(--mute)}
.tab[aria-pressed=true]{background:var(--accent);color:var(--accent-ink)}
.tab[aria-pressed=true] b{color:inherit;opacity:.85}
.ctl{display:flex;align-items:center;gap:.5rem;margin-top:.6rem}
.fwrap{position:relative}
.ctl .btn{padding:.25rem .6rem;font-size:.85rem}
.ctl .btn b{background:var(--ink);color:var(--bg);border-radius:999px;padding:0 .4rem;font-size:.72rem;line-height:1.3}
.sortw{display:flex;align-items:center;gap:.35rem;font-size:.85rem;color:var(--mute);min-width:0}
.sortw select{min-width:0;border:1px solid var(--line2);border-radius:6px;background:var(--surface);padding:.25rem .4rem;font-size:.85rem}
.btn.quiet{border-color:transparent;background:transparent;color:var(--mute);text-decoration:underline;text-underline-offset:2px}
.fpop{position:absolute;left:0;top:calc(100% + .35rem);z-index:25;width:16rem;max-width:calc(100vw - 1.5rem);background:var(--surface);
border:1px solid var(--line2);border-radius:8px;box-shadow:0 8px 24px rgba(10,18,24,.25);padding:.4rem .75rem .6rem}
.fpop fieldset{border:0;margin:.35rem 0 0;padding:0}
.fpop legend{padding:0;margin-bottom:.15rem;font-size:.72rem;font-weight:650;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.fpop label{display:flex;align-items:center;gap:.5rem;padding:.2rem 0;font-size:.9rem}
.fpop input{accent-color:var(--accent)}
.chips{display:flex;flex-wrap:wrap;gap:.35rem;margin-top:.5rem}
.fchip{display:inline-flex;align-items:center;gap:.25rem;border:1px solid var(--line2);background:var(--surface2);border-radius:999px;
padding:.05rem .35rem .05rem .6rem;font-size:.8rem;font-weight:550}
.fchip:hover{background:var(--line)}
.fchip svg.i{width:.9em;height:.9em}
.wo{display:grid;grid-template-columns:repeat(auto-fit,minmax(16rem,1fr));gap:0 1.5rem}
.wo-r{display:flex;justify-content:space-between;gap:.75rem;padding:.35rem .5rem;border-top:1px solid var(--line);border-radius:4px}
.wo-r .k{color:var(--mute)}
.wo-r .val{text-align:right;font-weight:600;overflow-wrap:anywhere}
.wo-r .val small{margin-left:.35rem;font-weight:500;color:var(--mute)}
.wo-r.hl{background:var(--accent-bg)}
.wo-none{margin:0}
.dot{width:.55rem;height:.55rem;border-radius:50%;background:var(--low)}
.dot.high{background:var(--high)}.dot.medium{background:var(--medium)}.dot.low{background:var(--low)}
.list{overflow:auto;flex:1;margin:0;padding:0;list-style:none}
.row{display:grid;grid-template-columns:4px 1fr auto;gap:.75rem;width:100%;text-align:left;border:0;border-bottom:1px solid var(--line);
background:transparent;padding:.65rem .75rem .65rem 0;align-items:center}
.row:hover{background:var(--surface2)}
.row[aria-current=true]{background:var(--accent-bg)}
.row .rk{align-self:stretch;background:var(--low)}
.row .rk.high{background:var(--high)}.row .rk.medium{background:var(--medium)}
.row .a,.row .b{display:block}
.row .a{font-weight:650;overflow-wrap:anywhere}
.row .b{color:var(--mute);font-size:.85rem;overflow-wrap:anywhere}
.row .r{display:flex;flex-direction:column;align-items:flex-end;gap:.25rem}
.amt{font-weight:600;white-space:nowrap}.amt.d{color:var(--dispute)}.amt.m{color:var(--mute);font-weight:500}
.empty{padding:1.5rem;color:var(--mute);text-align:center}
.pill{display:inline-flex;align-items:center;gap:.25rem;padding:.05rem .55rem;border-radius:999px;font-size:.78rem;font-weight:650;
border:1px dashed currentColor;white-space:nowrap}
.pill.set{border-style:solid;border-color:transparent}
.pill.approve{background:var(--approve-bg);color:var(--approve)}.pill.dispute{background:var(--dispute-bg);color:var(--dispute)}
.pill.hold{background:var(--hold-bg);color:var(--hold)}.pill.open{background:var(--low-bg);color:var(--low)}
.detail{overflow:auto;min-height:0}
.d-in{max-width:62rem;margin:0 auto;padding:0 1.25rem 3rem}
.dhead{position:sticky;top:0;z-index:2;background:var(--bg);display:flex;align-items:center;gap:.75rem;padding:.9rem 0 .6rem}
.dhead h2{margin:0;font-size:1.25rem;letter-spacing:-.01em;overflow-wrap:anywhere}
.dhead p{margin:0;color:var(--mute);font-size:.9rem;overflow-wrap:anywhere}
.nav{display:flex;align-items:center;gap:.35rem;font-size:.85rem;color:var(--mute);white-space:nowrap}
.back{display:none}
.next{margin:.25rem 0 .9rem}
.why{margin:0 0 .5rem;font-weight:600}
.next-row{display:flex;gap:.6rem;flex-wrap:wrap;align-items:flex-end}
.next-row label{display:grid;gap:.15rem;font-size:.75rem;font-weight:600;color:var(--mute)}
.next-row input[type=date]{border:1px solid var(--line2);border-radius:6px;background:var(--surface2);padding:.35rem .5rem}
.more{position:relative}
.more>summary{list-style:none;cursor:pointer}
.more>summary::-webkit-details-marker{display:none}
.more[open]>summary{background:var(--surface2)}
.menu{position:absolute;left:0;top:calc(100% + .25rem);z-index:20;width:min(23rem,calc(100vw - 1.5rem));background:var(--surface);
border:1px solid var(--line2);border-radius:8px;box-shadow:0 8px 24px rgba(10,18,24,.25);padding:.25rem}
.opt{display:block;width:100%;text-align:left;border:0;background:transparent;border-radius:6px;padding:.5rem .6rem}
.opt:hover:not([disabled]){background:var(--surface2)}
.opt b{display:block;font-weight:650}
.opt .d{display:block;color:var(--mute);font-size:.85rem;font-weight:400}
.opt[disabled]{opacity:.4;cursor:default}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.donel{font-weight:650}
.lnk{text-decoration:none;color:var(--ink)}
.cmp{width:100%;border-collapse:collapse;margin:0 0 .6rem}
.cmp th,.cmp td{text-align:right;padding:.3rem .5rem;border-top:1px solid var(--line)}
.cmp th:first-child,.cmp td:first-child{text-align:left;color:var(--mute);font-weight:550}
.cmp thead th{border-top:0;font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mute)}
.sec{scroll-margin-top:4.5rem}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr));gap:1px;background:var(--line);border:1px solid var(--line);
border-radius:8px;overflow:hidden}
.cell{background:var(--surface);padding:.6rem .8rem;min-width:0}
.cell .l{font-size:.72rem;color:var(--mute);text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.cell .v{font-weight:650;overflow-wrap:anywhere}.cell .v small{display:block;font-weight:500;color:var(--mute)}
.decided{margin-top:.6rem;background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--low);border-radius:8px;padding:.6rem .9rem;
display:grid;grid-template-columns:auto 1fr;gap:.2rem 1rem}
.decided.approve{border-left-color:var(--approve)}.decided.dispute{border-left-color:var(--dispute)}.decided.hold{border-left-color:var(--hold)}
.decided dt{color:var(--mute)}.decided dd{margin:0;overflow-wrap:anywhere}
.toolbar{display:flex;justify-content:flex-end;margin:1rem 0 .5rem}
.sec{background:var(--surface);border:1px solid var(--line);border-radius:8px;margin:0 0 .75rem}
.sec-h{display:flex;align-items:center;gap:.6rem;width:100%;border:0;background:transparent;padding:.7rem .9rem;text-align:left;font-weight:650;font-size:1rem}
.sec-h .n{color:var(--mute);font-weight:550}
.sec-h .ch{margin-left:auto;transition:transform .15s}
.sec-h[aria-expanded=false] .ch{transform:rotate(-90deg)}
.sec-b{padding:0 .9rem .9rem}
.find{display:grid;grid-template-columns:1fr auto;gap:.4rem 1rem;padding:.8rem 0;border-top:1px solid var(--line)}
.find:first-child{border-top:0}
.find .p{font-weight:600;overflow-wrap:anywhere}
.find .m{text-align:right;white-space:nowrap}
.find .m b{display:block}.find .m span{color:var(--mute);font-size:.85rem}
.tag{display:inline-block;margin-top:.2rem;padding:0 .45rem;border-radius:4px;font-size:.72rem;font-weight:650;background:var(--hold-bg);color:var(--hold)}
.quotes{grid-column:1 / -1;display:grid;grid-template-columns:auto 1fr;gap:.3rem .75rem;align-items:baseline}
.quotes .k{color:var(--mute);font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.quotes q{display:block;quotes:none;background:var(--quote);border-left:3px solid var(--line2);border-radius:0 4px 4px 0;padding:.3rem .6rem;
font:.82rem/1.45 var(--mono);overflow-wrap:anywhere;font-variant-numeric:normal}
.note{display:grid;grid-template-columns:auto 1fr;gap:.75rem;padding:.7rem 0 0;border-top:1px solid var(--line);align-items:baseline;overflow-wrap:anywhere}
.note .k{color:var(--mute);font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;font-weight:600}
.lt-bar{display:flex;gap:.5rem;flex-wrap:wrap;margin-top:.6rem;align-items:center}
textarea.letter{display:block;width:100%;min-height:12rem;resize:vertical;border:1px solid var(--line2);border-radius:6px;background:var(--surface2);
padding:.9rem 1rem;font:1rem/1.6 var(--serif);font-variant-numeric:normal}
pre.raw{margin:0;background:var(--quote);border-radius:6px;padding:.8rem;overflow:auto;font:.82rem/1.5 var(--mono);white-space:pre-wrap;overflow-wrap:anywhere}
pre.raw.en{font:.95rem/1.6 var(--serif)}
dialog{border:1px solid var(--line2);border-radius:10px;background:var(--surface);color:var(--ink);padding:0;width:min(30rem,calc(100vw - 2rem))}
dialog::backdrop{background:rgba(10,18,24,.55)}
.dlg-h{display:flex;align-items:center;justify-content:space-between;padding:.8rem 1rem;border-bottom:1px solid var(--line)}
.dlg-h h2{margin:0;font-size:1.05rem}
.dlg-b{display:grid;gap:.75rem;padding:1rem}
.dlg-b label{display:grid;gap:.25rem;font-weight:600;font-size:.85rem}
.dlg-b input[type=text]{border:1px solid var(--line2);border-radius:6px;background:var(--surface2);padding:.45rem .6rem;font-weight:400;font-size:1rem}
.seg{display:flex;gap:.5rem}
.seg label{flex:1;display:flex;align-items:center;gap:.5rem;border:1px solid var(--line2);border-radius:6px;padding:.4rem .6rem;font-weight:550}
.dlg-f{display:flex;gap:.75rem;align-items:center;justify-content:flex-end;padding:.8rem 1rem;border-top:1px solid var(--line)}
.err{margin:0 0 .9rem;color:var(--dispute);font-weight:600}
.warn{margin-top:.6rem;padding:.5rem .8rem;border:1px solid var(--medium);background:var(--medium-bg);color:var(--medium);border-radius:8px;font-weight:600}
.chg{display:grid;gap:.6rem;margin:0 0 .9rem;padding:.8rem;background:var(--surface);border:1px solid var(--line);border-radius:8px;max-width:34rem}
.chg label{display:grid;gap:.25rem;font-weight:600;font-size:.85rem}
.chg select,.chg input,.chg textarea{border:1px solid var(--line2);border-radius:6px;background:var(--surface2);padding:.45rem .6rem;font-weight:400;font-size:1rem}
.chg textarea{min-height:4.5rem;resize:vertical}
.chg .bt{display:flex;gap:.5rem}
.closed{margin:.6rem 0 0;padding:.45rem .8rem;border-radius:8px;background:var(--high-bg);color:var(--high);font-weight:650}
.mpick{border:1px solid var(--line2);border-radius:6px;background:var(--surface);padding:.35rem .6rem;font-weight:550}
.tag.small{background:var(--low-bg);color:var(--low);margin:0 .35rem 0 0}.tag.repeat{background:var(--high-bg);color:var(--high);margin:0 .35rem 0 0}
.row .a .tag{margin:0 0 0 .4rem;vertical-align:1px}.dhead h2 .tag{vertical-align:3px;margin-left:.4rem}
.grp{padding:.5rem .75rem;background:var(--surface2);border-bottom:1px solid var(--line);font-size:.75rem;font-weight:650;color:var(--mute);text-transform:uppercase;letter-spacing:.04em}
.pill.set.approve{background:var(--approve-bg)}
.banner{display:flex;align-items:center;justify-content:space-between;gap:.75rem;flex-wrap:wrap;margin:0 0 .6rem;padding:.6rem .8rem;border-radius:8px;border:1px solid var(--approve);background:var(--approve-bg);color:var(--approve);font-weight:650}
.banner.warn{border-color:var(--medium);background:var(--medium-bg);color:var(--medium)}
.banner .bt{display:flex;gap:.5rem;flex-wrap:wrap}.banner .btn{color:var(--ink)}.banner .btn.primary{color:var(--accent-ink)}
.refs{grid-column:1 / -1;display:flex;flex-wrap:wrap;gap:.4rem}.rd .refs{display:inline-flex;margin-left:.4rem;vertical-align:baseline}
.rds{display:grid;gap:.5rem}
.refw{display:inline-block}
.ref{border:0;background:var(--accent-bg);color:var(--accent);text-decoration:underline;text-underline-offset:2px;border-radius:4px;padding:0 .45rem;font-size:.8rem;font-weight:650}
.pop{position:fixed;z-index:30;width:min(24rem,calc(100vw - 1rem));background:var(--surface);color:var(--ink);border:1px solid var(--line2);border-radius:8px;
box-shadow:0 8px 24px rgba(10,18,24,.25);padding:.7rem .8rem;font-size:.88rem;line-height:1.45}
.pop p{margin:0 0 .5rem}.pop q{display:block;quotes:none;background:var(--quote);border-left:3px solid var(--line2);border-radius:0 4px 4px 0;padding:.3rem .6rem;font:.8rem/1.45 var(--mono);overflow-wrap:anywhere}
textarea.ask{min-height:7rem;resize:vertical;border:1px solid var(--line2);border-radius:6px;background:var(--surface2);padding:.6rem .75rem;font:.95rem/1.5 var(--serif)}
.btn.attn b{background:var(--ink);color:var(--bg);border-radius:999px;padding:0 .45rem;font-size:.8rem}
.att{display:grid;grid-template-columns:auto auto 1fr;gap:.2rem .75rem;text-align:left;width:100%;border:1px solid var(--line);border-radius:6px;background:var(--surface);padding:.55rem .7rem}
.att:hover:not([disabled]){background:var(--surface2)}.att .m{color:var(--mute)}
.dlg-b fieldset{border:1px solid var(--line);border-radius:8px;display:grid;gap:.75rem;margin:0;padding:.75rem}
.dlg-b legend{font-weight:650;padding:0 .35rem}
.dlg-b input[type=text]:disabled{opacity:.6}
.muted{color:var(--mute);font-size:.85rem}
@media (max-width:820px){
html,body{height:auto}
.app{display:block;height:auto}
.top{padding:.6rem .75rem}
.kpis{display:flex;overflow-x:auto;gap:.5rem;margin:.6rem -.75rem 0;padding:0 .75rem .15rem}
.kpi{flex:0 0 9.5rem}
.panes{display:block}
.queue{border-right:0}
.list{overflow:visible}
.d-in{padding:0 .75rem 3rem}
[data-view=list] .detail{display:none}
[data-view=detail] .queue{display:none}
.back{display:inline-flex}
.dhead{flex-wrap:wrap;top:0}
.dhead .t{flex:1;min-width:10rem}
.find{grid-template-columns:1fr}.find .m{text-align:left}
.quotes,.note{grid-template-columns:1fr;gap:.15rem}
.note .k{margin-top:.2rem}
}
@media print{.top,.queue,.dhead .btn,.next{display:none}.panes{display:block}.detail{overflow:visible}}
"""

JS = r"""
(function(){
'use strict';
var D=JSON.parse(document.getElementById('data').textContent);
var KEY='ovc.'+D.run;
function lsGet(k){try{return localStorage.getItem(k)}catch(e){return null}}
function lsSet(k,v){try{localStorage.setItem(k,v)}catch(e){}}
function lsDel(k){try{localStorage.removeItem(k)}catch(e){}}
function lsJson(k,d){var v=lsGet(k);if(!v)return d;try{var o=JSON.parse(v);return o&&typeof o==='object'?o:d}catch(e){return d}}
var S=Object.assign({},D.defaults,D.settings);
var UI=Object.assign({sel:null,filter:'all',sort:'risk'},lsJson(KEY+'.ui',{}));
UI.open=Object.assign({wo:true,findings:true,previous:true,letter:true,raw:false,en:false},UI.open||{});
UI.flt=Object.assign({risk:[],contractor:[],flags:[]},UI.flt&&typeof UI.flt==='object'?UI.flt:{});
['risk','contractor','flags'].forEach(function(k){if(!Array.isArray(UI.flt[k]))UI.flt[k]=[]});
var query='', view='list', byId={}, panel=null, ERR=null, DEAD=false, popId=0;
var LIVE=!!(D.live&&location.protocol.indexOf('http')===0);
function saveUI(){lsSet(KEY+'.ui',JSON.stringify(UI))}

function h(tag,a){
  var e=document.createElement(tag),k;
  for(k in (a||{})){var v=a[k];
    if(k==='class')e.className=v;
    else if(k.slice(0,2)==='on')e.addEventListener(k.slice(2),v);
    else if(v!==false&&v!=null)e.setAttribute(k,v);}
  for(var i=2;i<arguments.length;i++){var c=arguments[i];
    (Array.isArray(c)?c:[c]).forEach(function(x){if(x!=null&&x!==false)e.append(x.nodeType?x:document.createTextNode(String(x)))});}
  return e;
}
function ic(n){var s=document.createElementNS('http://www.w3.org/2000/svg','svg'),u=document.createElementNS('http://www.w3.org/2000/svg','use');
  s.setAttribute('class','i');s.setAttribute('aria-hidden','true');u.setAttribute('href','#i-'+n);s.append(u);return s}
function $(id){return document.getElementById(id)}
function clear(e){while(e.firstChild)e.removeChild(e.firstChild)}

// ---- data
function norm(c){return Object.assign({carried:true,number:'',date:'',findings:[],readings:[],letter:null,raw:'',en:'',risk:'',
  verdict:'',small:false,repeat:false,pay:'',total:'',by:'',warn:[],decision:null,addr:'',exec:'',wo_rec:null,
  ex:c.disputed_excl_vat||'0.00',inc:c.disputed_incl_vat||'0.00'},c)}
function index(){D.carried=(D.carried||[]).map(function(c){return c.carried?c:norm(c)});byId={};items().forEach(function(v){byId[v.id]=v})}
function items(){return D.invoices.concat(D.carried||[])}
function adopt(data){['invoices','carried','needs_attention','settings','total_ex','total_in'].forEach(function(k){D[k]=data[k]});
  S=Object.assign({},D.defaults,data.defaults,D.settings);index()}
index();

// ---- number format
function grp(i,sep){return i.replace(/\B(?=(\d{3})+(?!\d))/g,sep)}
function num(s){s=String(s);var neg=s.charAt(0)==='-';if(neg)s=s.slice(1);var p=s.split('.'),nl=S.num==='nl';
  return (neg?'-':'')+grp(p[0],nl?'.':',')+(p[1]?(nl?',':'.')+p[1]:'')}
function eur(s){return 'EUR '+num(s)}
function fmt(t){return String(t||'').replace(/EUR (-?\d+(?:\.\d+)?)/g,function(m,a){return 'EUR '+num(a)})}
function dsep(s){s=String(s);return S.num==='nl'?s.replace('.',','):s}
function undsep(s){s=String(s).trim();return S.num==='nl'?(s.indexOf(',')>=0?s.replace(/\./g,'').replace(',','.'):s):s.replace(/,/g,'')}
function isZero(s){return !s||Number(s)===0}
function plural(n,w){return n+' '+w+(n===1?'':'s')}
function nlDate(s){var m=/^(\d{4})-(\d{2})-(\d{2})/.exec(s||'');return m?m[3]+'-'+m[2]+'-'+m[1]:(s||'')}
function today(){var d=new Date(),p=function(n){return (n<10?'0':'')+n};return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate())}

// ---- letters
function compose(v){var L=v.letter,body=L.body;if(L.plain)return body+'\n';
  return L.head+'\n\n'+S.greeting+'\n\n'+body+'\n\n'+S.closing+'\n\n'+(S.signer?S.signer+'\n':'')+S.dept+'\n'}
function editKey(v){return KEY+'.letter.'+v.id}
function letterText(v){if(LIVE)return v.letter.saved;var e=lsGet(editKey(v));return e!==null?e:compose(v)}

// ---- statuses and filters
var STATUS={open:'To decide',to_pay:'Done',letter_ready:'Letter to send',waiting:'Waiting for contractor',resolved:'Done',on_hold:'On hold',disputed_full:'Done'};
var VERB={approve:'Pay',dispute:'Dispute',hold:'Hold'};
var PILL={to_pay:'approve',resolved:'approve',letter_ready:'dispute',disputed_full:'dispute',on_hold:'hold',waiting:'open'};
var TABS=[['decide','To decide'],['letters','Letters'],['waiting','Waiting'],['hold','On hold'],['done','Done'],['all','All']];
var RISKS=[['high','Look first'],['medium','Check'],['low','Clean']];
var FLAGS=[['small','Small only'],['repeat','Repeat only']];
var SORTS=[['risk','Risk'],['amt_desc','Amount high to low'],['amt_asc','Amount low to high'],['date','Invoice date'],['contractor','Contractor'],['days','Days waiting']];
if(!TABS.some(function(t){return t[0]===UI.filter}))UI.filter='all';
if(!SORTS.some(function(t){return t[0]===UI.sort}))UI.sort='risk';
function st(v){return v.status||'open'}
function pass(v,f){
  var s=st(v);
  if(f==='decide')return s==='open';
  if(f==='letters')return s==='letter_ready';
  if(f==='waiting')return s==='waiting';
  if(f==='hold')return s==='on_hold';
  if(f==='done')return s==='to_pay'||s==='resolved'||s==='disputed_full';
  return true}
function fltCount(){return UI.flt.risk.length+UI.flt.contractor.length+UI.flt.flags.length}
function passFlt(v){var f=UI.flt;
  if(f.risk.length&&f.risk.indexOf(v.risk)<0)return false;
  if(f.contractor.length&&f.contractor.indexOf(v.contractor)<0)return false;
  return f.flags.every(function(k){return !!v[k]})}
function passQ(v){return !query||(v.id+' '+v.contractor+' '+v.number+' '+v.wo).toLowerCase().indexOf(query)>=0}
function shown(v){return passFlt(v)&&passQ(v)}
function amtOf(v){var n=Number(isZero(v.inc)?v.total:v.inc);return isNaN(n)?0:n}
function dayOf(v){return v.days_waiting==null?-1:v.days_waiting}
var CMP={risk:function(){return 0},
  amt_desc:function(a,b){return amtOf(b)-amtOf(a)},amt_asc:function(a,b){return amtOf(a)-amtOf(b)},
  date:function(a,b){return (a.date||'').localeCompare(b.date||'')},
  contractor:function(a,b){return (a.contractor||'').localeCompare(b.contractor||'')},
  days:function(a,b){return dayOf(b)-dayOf(a)}};
function visible(){var all=items(),idx={};all.forEach(function(v,i){idx[v.id]=i});
  var cmp=CMP[UI.sort]||CMP.risk;
  return all.filter(function(v){return pass(v,UI.filter)&&shown(v)}).sort(function(a,b){
    return (a.carried?1:0)-(b.carried?1:0)||cmp(a,b)||idx[a.id]-idx[b.id]})}
function needsHer(v){var s=st(v);return s==='open'||s==='letter_ready'||(s==='waiting'&&!!v.update)}

function pillFor(v){
  var s=st(v);
  if(s==='open')return h('span',{class:'pill '+(v.verdict||'open')},v.verdict?VERB[v.verdict]:'To decide');
  return h('span',{class:'pill set '+(PILL[s]||'open')},s==='waiting'&&v.days_waiting!=null?'Waiting '+plural(v.days_waiting,'day'):STATUS[s]||s)}
function badges(v){var o=[];
  if(v.small)o.push(h('span',{class:'tag small'},'Small'));
  if(v.repeat)o.push(h('span',{class:'tag repeat'},'Repeat'));
  return o}

function renderTop(){
  var n=D.invoices.length,d=D.invoices.filter(function(v){return st(v)!=='open'}).length,
    hold=D.invoices.filter(function(v){return st(v)==='on_hold'}).length;
  var box=$('kpis');clear(box);
  function k(l,v,x){box.append(h('div',{class:'kpi'},h('div',{class:'l'},l),h('div',{class:'v'},v),x))}
  k('To dispute incl. VAT',eur(D.total_in));
  k('To dispute excl. VAT',eur(D.total_ex));
  k('Invoices',String(n));
  k('Decided',[String(d),h('small',{},' of '+n)],h('div',{class:'bar',role:'progressbar','aria-valuemin':0,'aria-valuemax':n,'aria-valuenow':d,'aria-label':'Decided'},
    h('i',{style:'width:'+(n?Math.round(100*d/n):0)+'%'})));
  k('On hold',String(hold));
  var na=(D.needs_attention||[]).length;$('attn').hidden=!na;$('attn-n').textContent=String(na);
}
function renderTabs(){
  var box=$('tabs');clear(box);
  TABS.forEach(function(t){var c=items().filter(function(v){return pass(v,t[0])&&shown(v)}).length;
    box.append(h('button',{class:'tab',type:'button','aria-pressed':String(UI.filter===t[0]),onclick:function(){setFilter(t[0])}},t[1],h('b',{},String(c))))});
  var on=box.querySelector('[aria-pressed=true]');if(on&&box.scrollWidth>box.clientWidth)box.scrollLeft=on.offsetLeft-(box.clientWidth-on.offsetWidth)/2;
  renderCtl()}
function labelOf(list,k){var x=list.filter(function(t){return t[0]===k})[0];return x?x[1]:k}
function toggleFlt(g,k,on){var a=UI.flt[g],i=a.indexOf(k);if(on&&i<0)a.push(k);if(!on&&i>=0)a.splice(i,1);filtersChanged()}
function filtersChanged(){saveUI();keepSel();renderTabs();renderList();renderDetail()}
function isDefault(){return !query&&!fltCount()&&UI.sort==='risk'}
function renderCtl(){
  var n=fltCount(),b=$('flt-n');b.textContent=String(n);b.hidden=!n;
  $('sort').value=UI.sort;$('clear').hidden=isDefault();
  var box=$('chips');clear(box);
  [['risk',RISKS],['contractor',null],['flags',FLAGS]].forEach(function(g){UI.flt[g[0]].forEach(function(k){
    box.append(h('button',{class:'fchip',type:'button','aria-label':'Remove filter '+(g[1]?labelOf(g[1],k):k),onclick:function(){toggleFlt(g[0],k,false);if(!$('flt-pop').hidden)fillPop()}},
      g[1]?labelOf(g[1],k):k,ic('x')))})});
  box.hidden=!n}
function fillPop(){
  var pop=$('flt-pop');clear(pop);
  function group(name,g,opts){var fs=h('fieldset',{},h('legend',{},name));
    opts.forEach(function(o){var cb=h('input',{type:'checkbox',onchange:function(){toggleFlt(g,o[0],cb.checked)}});cb.checked=UI.flt[g].indexOf(o[0])>=0;
      fs.append(h('label',{},cb,h('span',{},o[1])))});pop.append(fs)}
  group('Risk','risk',RISKS);
  var cs=[];items().forEach(function(v){if(!v.err&&v.contractor&&cs.indexOf(v.contractor)<0)cs.push(v.contractor)});cs.sort();
  group('Contractor','contractor',cs.map(function(c){return [c,c]}));
  group('Flags','flags',FLAGS)}
function setPop(open){var p=$('flt-pop');if(open)fillPop();p.hidden=!open;$('flt-btn').setAttribute('aria-expanded',String(open))}
function initQueue(){
  var sel=$('sort');SORTS.forEach(function(o){sel.append(h('option',{value:o[0]},o[1]))});
  sel.addEventListener('change',function(){UI.sort=sel.value;filtersChanged()});
  $('flt-btn').addEventListener('click',function(e){e.stopPropagation();setPop($('flt-pop').hidden)});
  $('flt-pop').addEventListener('click',function(e){e.stopPropagation()});
  document.addEventListener('click',function(){if(!$('flt-pop').hidden)setPop(false)});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&!$('flt-pop').hidden){setPop(false);$('flt-btn').focus()}});
  $('clear').addEventListener('click',function(){query='';$('q').value='';UI.flt={risk:[],contractor:[],flags:[]};UI.sort='risk';
    if(!$('flt-pop').hidden)fillPop();filtersChanged()})}
function rowFor(v){
  var disp=!isZero(v.inc);
  return h('li',{},h('button',{class:'row',type:'button','data-id':v.id,'aria-current':String(v.id===UI.sel),onclick:function(){if(v.carried&&LIVE&&v.month)goTo(v.id,v.month);else select(v.id,true)}},
    h('span',{class:'rk '+(v.risk||'')}),
    h('span',{},h('span',{class:'a'},v.id,badges(v)),h('span',{class:'b'},[v.contractor,v.wo,v.carried?v.month:''].filter(Boolean).join(' · '))),
    h('span',{class:'r'},h('span',{class:'amt '+(disp?'d':'m')},disp?eur(v.inc):(v.total?eur(v.total):'')),pillFor(v))))}
function renderList(){
  var ul=$('list'),vis=visible();clear(ul);
  if(!vis.length){ul.append(h('li',{class:'empty'},'No invoices'));return}
  vis.filter(function(v){return !v.carried}).forEach(function(v){ul.append(rowFor(v))});
  var car=vis.filter(function(v){return v.carried});
  if(car.length){ul.append(h('li',{class:'grp'},'From earlier months'));car.forEach(function(v){ul.append(rowFor(v))})}
}
function renderAll(){renderTop();renderTabs();renderList();renderDetail()}

function setFilter(f){UI.filter=f;saveUI();keepSel();renderTabs();renderList();renderDetail()}
function keepSel(){var vis=visible();if(vis.length&&!vis.some(function(v){return v.id===UI.sel})&&window.innerWidth>820)UI.sel=vis[0].id;saveUI()}
function select(id,show){UI.sel=id;saveUI();panel=null;ERR=null;hidePops();if(show)setView('detail');renderList();renderDetail();
  var row=document.querySelector('.row[data-id="'+CSS.escape(id)+'"]');if(row)row.scrollIntoView({block:'nearest'});$('detail').scrollTop=0;window.scrollTo(0,0)}
function step(d){var vis=visible(),i=vis.findIndex(function(v){return v.id===UI.sel});
  if(!vis.length)return;var j=i<0?(d>0?0:vis.length-1):i+d;if(j<0||j>=vis.length)return;select(vis[j].id,false)}
function setView(v){view=v;document.body.setAttribute('data-view',v)}
function monthOf(id){var v=byId[id];if(v)return v.carried?v.month:(v.date||'').slice(0,7);
  var a=(D.needs_attention||[]).filter(function(x){return x.invoice===id})[0];return a?a.month:''}
function goTo(id,month){
  var v=byId[id];
  if(v&&!(v.carried&&LIVE)){
    if(!pass(v,UI.filter)){UI.filter='all';saveUI()}
    if(!passFlt(v)){UI.flt={risk:[],contractor:[],flags:[]};saveUI()}
    if(!passQ(v)){query='';$('q').value=''}
    select(id,true);renderTabs();$('detail').scrollIntoView({block:'start'});return}
  var m=month||monthOf(id);
  if(LIVE&&m)location.href='/?month='+encodeURIComponent(m)+'&invoice='+encodeURIComponent(id)}
function link(id,month,text){
  var a=h('a',{class:'btn lnk',href:LIVE?'/?month='+encodeURIComponent(month||'')+'&invoice='+encodeURIComponent(id):'#invoice='+encodeURIComponent(id)},text);
  a.addEventListener('click',function(e){e.preventDefault();goTo(id,month)});return a}

// ---- reference chips with popover
var pinned=null;
function hidePops(){Array.prototype.forEach.call(document.querySelectorAll('.pop'),function(p){p.hidden=true});
  Array.prototype.forEach.call(document.querySelectorAll('.ref[aria-expanded=true]'),function(b){b.setAttribute('aria-expanded','false')});pinned=null}
function refChip(r){
  var id='pop'+(++popId),pop=h('div',{class:'pop',role:'tooltip',id:id,hidden:'hidden'},h('p',{},r.explain),r.quote?h('q',{},r.quote):null),
    b=h('button',{class:'ref',type:'button','aria-expanded':'false','aria-describedby':id},r.label);
  function show(){hidePops();pop.hidden=false;b.setAttribute('aria-expanded','true');
    var rc=b.getBoundingClientRect(),w=pop.offsetWidth,ph=pop.offsetHeight;
    var left=Math.max(8,Math.min(rc.left,window.innerWidth-w-8)),top=rc.bottom+6;
    if(top+ph>window.innerHeight-8&&rc.top-ph-6>8)top=rc.top-ph-6;
    pop.style.left=left+'px';pop.style.top=top+'px'}
  function hide(){pop.hidden=true;b.setAttribute('aria-expanded','false')}
  var timer=0;
  function later(fn,ms){clearTimeout(timer);timer=setTimeout(fn,ms)}
  function enter(){later(function(){if(!pinned)show()},120)}
  function leave(){later(function(){if(pinned!==b)hide()},180)}
  b.addEventListener('mouseenter',enter);b.addEventListener('mouseleave',leave);
  pop.addEventListener('mouseenter',function(){clearTimeout(timer)});pop.addEventListener('mouseleave',leave);
  b.addEventListener('focus',function(){clearTimeout(timer);if(!pinned)show()});
  b.addEventListener('blur',function(){if(pinned!==b)hide()});
  b.addEventListener('click',function(e){e.stopPropagation();if(pinned===b){pinned=null;hide()}else{show();pinned=b}});
  pop.addEventListener('click',function(e){e.stopPropagation()});
  return h('span',{class:'refw'},b,pop)}
document.addEventListener('click',hidePops);
document.addEventListener('scroll',hidePops,true);
document.addEventListener('keydown',function(e){if(e.key==='Escape')hidePops()});

// ---- detail
var SECS=[['wo','Work order'],['findings','Findings'],['letter','Letter'],['raw','Original invoice'],['en','English translation'],['previous','Previous version']];
function copyText(t,btn,label){
  function done(){var o=label;btn.lastChild.textContent='Copied';setTimeout(function(){btn.lastChild.textContent=o},1500)}
  function fb(){var ta=h('textarea',{style:'position:fixed;opacity:0'});ta.value=t;document.body.append(ta);ta.select();
    try{document.execCommand('copy')}catch(e){}ta.remove();done()}
  if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(t).then(done,fb);else fb()}
function btn(cls,icon,label,fn){var b=h('button',{type:'button',class:cls,onclick:function(){fn(b)}},icon?ic(icon):null,h('span',{},label));return b}

// ---- live decisions (served by the MCP server; absent in the file snapshot)
function api(path,body){
  return fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Token':D.live.token},body:JSON.stringify(body)}).then(function(r){
    return r.json().catch(function(){return {}}).then(function(j){if(!r.ok||!j.ok)throw new Error(j.error||'Could not save. Try again.');return j})},
    function(){markDead();throw new Error('Dashboard closed. Open Claude to continue.')})}
function markDead(){if(DEAD)return;DEAD=true;$('closed').hidden=false;renderDetail()}
function decide(v,payload,b,advance){
  ERR=null;if(b)b.disabled=true;
  var ids=visible().map(function(x){return x.id}),i=ids.indexOf(v.id);
  api('/api/decision',Object.assign({invoice:v.id,month:D.live.month},payload)).then(function(j){
    adopt(j.data);panel=null;
    if(advance==='letter'){UI.filter='letters';UI.open.letter=true;saveUI();keepSel();renderAll();
      var ls=$('sec-letter');if(ls)ls.scrollIntoView({behavior:'smooth',block:'start'});return}
    if(!advance){keepSel();renderAll();return}
    if(b){b.lastChild.textContent='Saved';b.disabled=false}
    renderTop();renderTabs();renderList();
    setTimeout(function(){
      var later=ids.slice(i+1),need=visible().filter(needsHer),
        nx=need.filter(function(x){return later.indexOf(x.id)>=0})[0]||need[0];
      if(nx&&nx.id!==v.id)select(nx.id,false);else{keepSel();renderAll()}},700)
  },function(e){ERR={id:v.id,text:e.message};if(b)b.disabled=false;renderDetail()})}

var NOSEND=' Nothing is sent.';
var LABEL={pay:'Approve for payment',payany:'Approve for payment anyway',hold:'Put on hold',disagree:'Change outcome',letter_ok:'Prepare dispute letter',
  let_go:'Approve: small amount',sent:'Mark letter as sent',undo:'Undo',release:'Release hold',credit:'Close dispute: credit note matches',corrected:'Close dispute: corrected invoice received',
  cright:'Close dispute: contractor was right',withdraw:'Withdraw dispute',close:'Close dispute',ask:'Ask housing officer to confirm',
  confirmed:'Work order confirmed',reject:'Reject invoice'};
var DESC={pay:'Records that this invoice is approved for payment.'+NOSEND,
  payany:'Approves payment although a dispute was proposed. You give a reason.'+NOSEND,
  hold:'Records that this invoice is on hold until it is cleared up.'+NOSEND,
  disagree:'Lets you set a different outcome and amount, with a reason.'+NOSEND,
  letter_ok:'Accepts the proposed dispute and opens the letter for you to read and edit.'+NOSEND,
  let_go:'Accepts this small amount and approves the invoice for payment. A reason is needed when it keeps coming back.'+NOSEND,
  sent:'Records that you sent the letter, on the date you pick.'+NOSEND,
  undo:'Removes your last decision on this invoice.'+NOSEND,
  release:'Removes the hold so the invoice goes back to To decide.'+NOSEND,
  credit:'Records that the credit note matches the dispute and closes it.'+NOSEND,
  corrected:'Records that the corrected invoice replaces the disputed one and closes the dispute.'+NOSEND,
  cright:'Records that the contractor was right and closes the dispute. You give a reason.'+NOSEND,
  withdraw:'Records that you withdrew the dispute and closes it. You give a reason.'+NOSEND,
  close:'Closes the dispute after you choose how it ended and give a reason.'+NOSEND,
  ask:'Shows a message in Dutch for the housing officer, ready to copy.'+NOSEND,
  confirmed:'Records that the housing officer confirmed the work order.'+NOSEND,
  reject:'Disputes the whole invoice. You choose the reason.'+NOSEND};
var REASONS=['Work order not confirmed by the housing officer','Duplicate of an earlier invoice','Work not carried out','Other (write your own)'];
var KINDS=[['credit_note','Credit note received'],['corrected_invoice','Corrected invoice received'],['contractor_right','Contractor was right'],['withdrawn','Withdrawn']];
function holdy(v){return st(v)==='on_hold'||v.verdict==='hold'||v.findings.some(function(f){return f.hold})}
function hasRepeat(v){return v.repeat||v.findings.some(function(f){return f.repeat})}

function askText(v){
  return 'Goedendag,\n\nKunt u laten weten of er een werkorder bestaat voor '+v.wo+(v.addr?' op '+v.addr:'')+'? Er is een factuur van '+
    v.contractor+(v.number?' (nr. '+v.number+')':'')+(v.date?' van '+nlDate(v.date):'')+
    ' binnengekomen, maar de werkorder staat niet in onze lijst.\n\nAlvast bedankt.'}

function openPanel(v,kind,fixed){
  panel=panel&&panel.id===v.id&&panel.kind===kind&&panel.fixed===fixed?null:{id:v.id,kind:kind,fixed:fixed};ERR=null;renderDetail();var pn=document.querySelector('.chg');if(pn)pn.scrollIntoView({block:'nearest'})}

// The one suggested step and the other allowed steps for this invoice, with a plain reason.
function plan(v){
  var A=v.actions||[],has=function(a){return A.indexOf(a)>=0},s=st(v),u=v.update,P=null,M=[],why='',dt=null,done=false;
  function I(key,run){return {key:key,label:LABEL[key],desc:DESC[key],run:run}}
  function dec(d,extra,adv){return function(b){decide(v,Object.assign({decision:d},extra||{}),b,adv===undefined?true:adv)}}
  var undo=has('undo')?I('undo',dec('undo',null,false)):null;
  var reject=has('not_ours')?I('reject',function(){openPanel(v,'reject')}):null;
  var change=has('disagree')?I('disagree',function(){openPanel(v,'disagree')}):null;
  function firstFinding(){var f=v.findings[0];if(!f)return '';var t=fmt(f.plain).replace(/\.$/,'');
    if(v.findings.length>1)return plural(v.findings.length,'problem')+' found'+(isZero(v.inc)?'':', '+eur(v.inc)+' incl. VAT disputed');
    return t+(isZero(v.inc)?'':': '+eur(v.inc)+' incl. VAT disputed')}
  if(s==='to_pay'||s==='resolved'||s==='disputed_full'){done=true;M=[undo]}
  else if(s==='letter_ready'){
    why='The dispute letter for '+eur(v.inc)+' incl. VAT is ready to send.';
    dt=h('input',{type:'date',value:today(),max:today(),'aria-label':'Date sent'});
    P=has('sent')?I('sent',function(b){decide(v,{decision:'sent',date:dt.value||today()},b,true)}):null;M=[undo]}
  else if(s==='waiting'){
    var credit=u&&u.update==='credit_received';
    why=(v.days_waiting!=null?'Waiting '+plural(v.days_waiting,'day')+' for the contractor.':'Waiting for the contractor.')+(u?' '+updateText(v)+'.':'');
    if(has('resolved')){
      if(credit){
        P=I('credit',dec('resolved',{kind:'credit_note',linked_invoice:u.linked_invoice,reason:'Credit note '+u.linked_invoice+' received'}));
        M=[I('cright',function(){openPanel(v,'close','contractor_right')}),I('withdraw',function(){openPanel(v,'close','withdrawn')})]}
      else if(u&&u.update==='correction_received'){
        P=I('corrected',dec('resolved',{kind:'corrected_invoice',linked_invoice:u.linked_invoice,reason:'Corrected invoice '+u.linked_invoice+' received'}));
        M=[I('cright',function(){openPanel(v,'close','contractor_right')}),I('withdraw',function(){openPanel(v,'close','withdrawn')})]}
      else P=I('close',function(){openPanel(v,'close')})}
    M.push(undo)}
  else if(has('confirmed')){
    why='Work order '+v.wo+' is not in our list.';
    P=I('ask',function(){openPanel(v,'ask')});
    M=[I('confirmed',dec('confirmed')),reject,undo]}
  else if(s==='on_hold'){
    why=v.findings.length?firstFinding():'This invoice is on hold.';
    P=undo&&I('release',dec('undo',null,false));M=[change,reject]}
  else if(s==='open'){
    var hold=has('hold')?I('hold',dec('hold')):null,any=has('pay')?I('payany',function(){openPanel(v,'pay')}):null;
    if(v.verdict==='approve'){
      why=v.findings.length?'Small differences only: '+eur(v.ex)+' excl. VAT.':'Prices, hours and VAT match the contract.';
      P=has('pay')?I('pay',dec('pay')):null;M=[hold,change,reject]}
    else if(v.verdict==='dispute'){
      why=firstFinding();
      P=has('letter_ok')?I('letter_ok',dec('letter_ok',null,'letter')):null;
      M=[any,has('let_go')?I('let_go',function(b){if(hasRepeat(v))openPanel(v,'let_go');else decide(v,{decision:'let_go'},b,true)}):null,hold,change,reject]}
    else{why=firstFinding()||'This invoice needs a check before payment.';P=hold;M=[any,change,reject]}}
  M=M.filter(Boolean);
  return {P:P,M:M,why:why,dt:dt,done:done}}

function actionArea(v){
  var pl=plan(v),box=h('section',{class:'next','aria-label':'Next step'});
  function descId(){return 'dsc'+(++popId)}
  if(pl.why)box.append(h('p',{class:'why'},pl.why));
  var row=h('div',{class:'next-row'});
  if(pl.done)row.append(h('span',{class:'donel'},'Done'+(v.decision&&v.decision.date?' on '+v.decision.date:'')));
  if(pl.dt)row.append(h('label',{},'Date sent',pl.dt));
  if(pl.P){var id=descId(),pb=h('button',{type:'button',class:'btn primary',title:pl.P.desc,'aria-describedby':id,onclick:function(){pl.P.run(pb)}},
      h('span',{},pl.P.label),h('span',{class:'sr',id:id},pl.P.desc));if(DEAD)pb.disabled=true;row.append(pb)}
  if(pl.M.length){
    var det=h('details',{class:'more'},h('summary',{class:'btn'},h('span',{},'More options'),ic('chevron-down'))),menu=h('div',{class:'menu'});
    pl.M.forEach(function(it){var oid=descId(),ob=h('button',{type:'button',class:'opt',title:it.desc,'aria-describedby':oid,onclick:function(){det.open=false;it.run(ob)}},
        h('b',{},it.label),h('span',{class:'d',id:oid},it.desc));if(DEAD)ob.disabled=true;menu.append(ob)});
    det.append(menu);row.append(det)}
  box.append(row);
  if(panel&&panel.id===v.id)box.append(panelUI(v));
  if(ERR&&ERR.id===v.id)box.append(h('p',{class:'err',role:'alert'},ERR.text));
  return box}
function closeMenus(except){Array.prototype.forEach.call(document.querySelectorAll('details.more[open]'),function(d){if(!except||!d.contains(except))d.open=false})}
document.addEventListener('click',function(e){closeMenus(e.target)});
document.addEventListener('keydown',function(e){if(e.key==='Escape')closeMenus()});

function panelUI(v){
  var k=panel.kind,parts=[],save,why=null,sync=function(){},
    warn=h('p',{class:'err',role:'alert',hidden:'hidden'},'Write a reason.'),ready=function(){return !why||!!why.value.trim()};
  function guard(fn){return function(b){if(!ready()){warn.hidden=false;return}fn(b)}}
  function reasonField(){why=h('textarea',{maxlength:'500','aria-label':'Reason'});why.addEventListener('input',function(){sync()});return h('label',{},'Reason',why)}
  function close(){panel=null;renderDetail()}
  var cancel=btn('btn','x','Cancel',close);
  if(k==='ask'){
    var ta=h('textarea',{class:'ask',readonly:'readonly','aria-label':'Message to the housing officer'});ta.value=askText(v);
    parts=[ta];
    save=btn('btn primary','copy','Copy message',function(b){copyText(ta.value,b,'Copy message')});
    if(st(v)!=='on_hold'&&LIVE)parts.push(h('div',{class:'bt'},btn('btn','check','Put on hold',function(b){decide(v,{decision:'hold'},b,true)})));
  }else if(k==='disagree'){
    var sel=h('select',{'aria-label':'Verdict'},['approve','dispute','hold'].map(function(a){return h('option',{value:a},VERB[a])}));sel.value=v.verdict||'dispute';
    var amt=h('input',{type:'text',inputmode:'decimal','aria-label':'Amount excl. VAT'});
    amt.value=dsep(v.decision&&v.decision.amount?v.decision.amount:(isZero(v.ex)?'':v.ex));
    var aw=h('label',{},'Amount excl. VAT',amt);
    parts=[h('label',{},'Verdict',sel),aw,reasonField()];
    save=btn('btn primary','check','Save',guard(function(b){
      var p={decision:'disagree',verdict:sel.value,reason:why.value.trim()};
      if(sel.value==='dispute'&&amt.value.trim())p.amount=undsep(amt.value);
      decide(v,p,b,true)}));
    sync=function(){aw.hidden=sel.value!=='dispute';save.disabled=DEAD||!why.value.trim()};
    sel.addEventListener('change',function(){sync()});
  }else if(k==='close'){
    var kind=h('select',{'aria-label':'How it ended'},KINDS.map(function(x){return h('option',{value:x[0]},x[1])}));
    if(v.update&&v.update.update==='correction_received')kind.value='corrected_invoice';
    if(panel.fixed)kind.value=panel.fixed;
    parts=[panel.fixed?null:h('label',{},'How it ended',kind),reasonField()];
    save=btn('btn primary','check',panel.fixed==='withdrawn'?LABEL.withdraw:panel.fixed?LABEL.cright:LABEL.close,guard(function(b){
      var p={decision:'resolved',kind:kind.value,reason:why.value.trim()};
      var l=v.linked_invoice||(v.update&&v.update.linked_invoice);if(l&&(kind.value==='credit_note'||kind.value==='corrected_invoice'))p.linked_invoice=l;
      decide(v,p,b,true)}));
    sync=function(){save.disabled=DEAD||!why.value.trim()};
  }else if(k==='reject'){
    var rs=h('select',{'aria-label':'Reason'},REASONS.map(function(x,i){return h('option',{value:String(i)},x)})),
      own=h('textarea',{maxlength:'500','aria-label':'Your reason'}),ow=h('label',{},'Your reason',own);
    parts=[h('label',{},'Reason',rs),ow];
    why={get value(){return rs.value==='3'?own.value:'x'}};
    save=btn('btn primary','check',LABEL.reject,guard(function(b){
      var other=rs.value==='3';decide(v,{decision:'not_ours',reason:other?own.value.trim():REASONS[+rs.value]},b,true)}));
    sync=function(){var o=rs.value==='3';ow.hidden=!o;save.disabled=DEAD||(o&&!own.value.trim())};
    rs.addEventListener('change',function(){sync()});own.addEventListener('input',function(){sync()});
  }else{
    var lb={pay:LABEL.payany,let_go:LABEL.let_go}[k]||k;
    parts=[reasonField()];
    save=btn('btn primary','check',lb,guard(function(b){decide(v,{decision:k,reason:why.value.trim()},b,true)}));
    sync=function(){save.disabled=DEAD||!why.value.trim()};
  }
  var s0=sync;sync=function(){s0();if(ready())warn.hidden=true};sync();
  return h('div',{class:'chg'},parts,warn,h('div',{class:'bt'},save,cancel))}

function cell(l,v,sub){return h('div',{class:'cell'},h('div',{class:'l'},l),h('div',{class:'v'},v,sub?h('small',{},sub):null))}

function findingRow(f){
  return h('div',{class:'find'},
    h('div',{class:'p'},f.small?h('span',{class:'tag small'},'Small'):null,f.repeat?h('span',{class:'tag repeat'},'Repeat'):null,
      f.hold?h('span',{class:'tag'},'Hold'):f.provisional?h('span',{class:'tag'},'Provisional'):null,fmt(f.plain)),
    h('div',{class:'m'},f.ex&&!isZero(f.ex)||f.in&&!isZero(f.in)?[h('b',{},eur(f.in)+' incl.'),h('span',{},eur(f.ex)+' excl.')]:null),
    f.refs.length?h('div',{class:'refs'},f.refs.map(refChip)):null,
    f.inv?h('div',{class:'quotes'},h('span',{class:'k'},'Invoice'),h('q',{},f.inv)):null)}

var WOHL={R1:['exec'],R4:['type'],R5:['type'],R6:['max','mu'],R8:['ga'],R9:['ga'],R10:['built'],R12:['ga'],R13:['number'],R16:['address','supplier']};
function woUI(v){
  var w=v.wo_rec;
  if(!w.known)return h('p',{class:'wo-none'},w.id+' is not in the work order list.');
  var hl={};(v.findings||[]).forEach(function(f){(WOHL[f.rule]||[]).forEach(function(k){hl[k]=1})});
  function r(k,l,val,sub){return h('div',{class:'wo-r'+(hl[k]?' hl':''),title:hl[k]?'A finding on this invoice relies on this':null},
    h('span',{class:'k'},l),h('span',{class:'val'},val,sub?h('small',{},sub):null))}
  function hrs(x){return String(Number(x))+' h'}
  return h('div',{class:'wo'},
    r('number','Number',w.id),
    r('type','Type',w.type==='spoed'?'Emergency':w.type==='regulier'?'Regular':w.type,w.type),
    r('address','Address',w.address),
    r('supplier','Contractor',w.supplier),
    w.job?r('job','Job',w.job):null,
    v.exec?r('exec','Execution date',nlDate(v.exec)):null,
    r('built','Build year',String(w.built)),
    r('max','Maximum hours',hrs(w.max_hours)),
    r('mu','Approved extra hours',w.mu?w.mu+(Number(w.mu_hours)?' \u00b7 '+hrs(w.mu_hours):''):'None'),
    r('ga','Approval for extra work',w.ga?w.ga+(w.ga_eur!=null?' \u00b7 '+eur(w.ga_eur):''):'None'))}

function sectionBody(k,v){
  if(k==='wo')return woUI(v);
  if(k==='findings'){
    var n=[];
    if(!v.findings.length)n.push(h('div',{class:'empty'},'No findings'));
    v.findings.forEach(function(f){n.push(findingRow(f))});
    if((v.readings||[]).length)n.push(h('div',{class:'note'},h('span',{class:'k'},'How we read the contract here'),
      h('div',{class:'rds'},v.readings.map(function(r){return h('div',{class:'rd'},h('span',{},fmt(r.plain)),r.refs.length?h('span',{class:'refs'},r.refs.map(refChip)):null)}))));
    return n}
  if(k==='letter')return letterUI(v);
  if(k==='previous')return previousUI(v);
  if(k==='raw')return h('pre',{class:'raw'},v.raw);
  return h('pre',{class:'raw en'},v.en)}

function fit(ta){ta.style.height='auto';ta.style.height=Math.max(ta.scrollHeight+2,200)+'px'}
function letterUI(v){
  var ta=h('textarea',{class:'letter',spellcheck:'false','aria-label':'Letter text'});ta.value=letterText(v);
  var chip=h('span',{class:'chip'},'Edited');chip.hidden=lsGet(editKey(v))===null;chip.id='edited-chip';
  ta.addEventListener('input',function(){var c=compose(v);if(ta.value===c)lsDel(editKey(v));else lsSet(editKey(v),ta.value);
    chip.hidden=lsGet(editKey(v))===null;fit(ta)});
  ta.id='letter-ta';
  if(LIVE){
    var dirty=h('span',{class:'chip'},'Unsaved'),lerr=h('span',{class:'err',role:'alert'});dirty.hidden=true;lerr.style.margin='0';
    ta.addEventListener('input',function(){dirty.hidden=ta.value===v.letter.saved;fit(ta)});
    var sv=btn('btn primary','check','Save',function(b){lerr.textContent='';
      api('/api/letter',{invoice:v.id,month:D.live.month,text:ta.value}).then(function(){v.letter.saved=ta.value;dirty.hidden=true;
        b.lastChild.textContent='Saved';setTimeout(function(){b.lastChild.textContent='Save'},1500)},function(e){lerr.textContent=e.message})});
    if(DEAD)sv.disabled=true;
    return [ta,h('div',{class:'lt-bar'},sv,btn('btn','copy','Copy',function(b){copyText(ta.value,b,'Copy')}),
      btn('btn','rotate-ccw','Reset',function(){ta.value=compose(v);dirty.hidden=ta.value===v.letter.saved;fit(ta)}),dirty,lerr)]}
  var bar=h('div',{class:'lt-bar'},
    btn('btn primary','copy','Copy',function(b){copyText(ta.value,b,'Copy')}),
    btn('btn','rotate-ccw','Reset',function(){lsDel(editKey(v));ta.value=compose(v);chip.hidden=true;fit(ta)}),
    btn('btn','download','Save .txt',function(){var a=h('a',{href:URL.createObjectURL(new Blob([ta.value],{type:'text/plain;charset=utf-8'})),download:v.id+'.txt'});
      document.body.append(a);a.click();setTimeout(function(){URL.revokeObjectURL(a.href);a.remove()},500)}),chip);
  return [ta,bar]}

// ---- credit notes and corrections, linked both ways
function updateText(v){
  var u=v.update,m=u.month,l=u.linked_invoice;
  if(u.update==='credit_received')return 'Credit note received in '+m+': '+l+', matches';
  if(u.update==='credit_partial'){
    var inc=v.decision&&v.decision.amount_incl?v.decision.amount_incl:v.inc,rest=u.remaining_incl_vat;
    if(!isZero(inc)&&rest!=null&&rest!=='')return 'Credit note received in '+m+': '+l+', covers '+num((Number(inc)-Number(rest)).toFixed(2))+' of '+num(inc)+', '+num(rest)+' still open';
    return 'Credit note received in '+m+': '+l+', covers part of the dispute'}
  if(u.update==='credit_mismatch')return 'Credit note received in '+m+': '+l+', does not match';
  return 'Replaced by '+l+' ('+m+')'}
function previousUI(v){
  var p=v.previous,out=[];
  function row(l,a,b){return h('tr',{},h('td',{},l),h('td',{},a),h('td',{},b))}
  out.push(h('table',{class:'cmp'},h('thead',{},h('tr',{},h('th',{},''),h('th',{},'Previous '+p.invoice),h('th',{},'New '+v.id))),
    h('tbody',{},row('Invoice total',eur(p.total),eur(v.total)),row('Disputed incl. VAT',eur(p.inc),eur(v.inc)),row('Disputed excl. VAT',eur(p.ex),eur(v.ex)),row('Payable',eur(p.pay),eur(v.pay)))));
  if(!p.findings.length)out.push(h('div',{class:'empty'},'No findings on the previous version'));
  p.findings.forEach(function(f){out.push(h('div',{class:'find'},h('div',{class:'p'},fmt(f.plain)),
    h('div',{class:'m'},!isZero(f.ex)||!isZero(f.in)?[h('b',{},eur(f.in)+' incl.'),h('span',{},eur(f.ex)+' excl.')]:null)))});
  out.push(h('pre',{class:'raw'},p.raw));
  return out}
function banners(v){
  var out=[];
  if(v.update){var u=v.update,ok=u.update==='credit_received'||u.update==='correction_received';
    out.push(h('div',{class:'banner '+(ok?'ok':'warn'),role:'status'},h('span',{},updateText(v)),
      h('span',{class:'bt'},link(u.linked_invoice,u.month,'Open '+u.linked_invoice))))}
  if(v.link&&v.link.kind==='credit_note'){var l=v.link,mo=(v.previous&&v.previous.month)||monthOf(l.invoice),
      what='Credits '+l.invoice+(mo?' ('+mo+')':'')+
        (l.match==='partial'?', covers part':l.match==='over'?', more than the dispute':'');
    out.push(h('div',{class:'banner '+(l.match==='over'?'warn':'ok')},h('span',{},what),
      h('span',{class:'bt'},link(l.invoice,mo,'Open '+l.invoice))))}
  return out}

function statusCell(v){
  var s=st(v),lbl=STATUS[s]||s,sub=[];
  if(s==='to_pay')sub.push('to pay');if(s==='disputed_full')sub.push('whole invoice disputed');
  if(s==='waiting'&&v.days_waiting!=null)sub.push(plural(v.days_waiting,'day'));
  if(v.sent_date&&(s==='waiting'||s==='resolved'))sub.push('sent '+v.sent_date);
  if(s==='resolved'&&v.resolved_kind)sub.push((KINDS.filter(function(x){return x[0]===v.resolved_kind})[0]||[0,v.resolved_kind])[1].toLowerCase());
  return cell('Status',h('span',{class:'pill '+(s==='open'?'open':'set '+(PILL[s]||'open'))},lbl),sub.join(', '))}

function renderDetail(){
  var box=$('detail'),v=byId[UI.sel],keepTop=box.scrollTop;clear(box);
  if(!v){box.append(h('div',{class:'empty'},'No invoice selected'));return}
  var vis=visible(),pos=vis.findIndex(function(x){return x.id===v.id});
  var inner=h('div',{class:'d-in'});
  inner.append(h('div',{class:'dhead'},
    btn('btn back','arrow-left','Back',function(){setView('list')}),
    h('div',{class:'t'},h('h2',{},v.id,' ',badges(v)),h('p',{},[v.contractor,v.number,v.wo,v.carried?v.month:v.date].filter(Boolean).join(' · '))),
    h('div',{class:'nav'},pos>=0?(pos+1)+' of '+vis.length:null,
      h('button',{class:'btn icon',type:'button','aria-label':'Previous',title:'Previous (k)',onclick:function(){step(-1)}},ic('chevron-left')),
      h('button',{class:'btn icon',type:'button','aria-label':'Next',title:'Next (j)',onclick:function(){step(1)}},ic('chevron-right')))));
  if(LIVE&&!v.err&&!v.carried)inner.append(actionArea(v));
  banners(v).forEach(function(x){inner.append(x)});
  var d=v.decision;
  inner.append(h('div',{class:'strip'},
    v.verdict?cell('Proposal',h('span',{class:'pill '+v.verdict},VERB[v.verdict])):null,
    statusCell(v),
    cell('Disputed',eur(v.inc),eur(v.ex)+' excl.'),
    v.carried?null:cell('Payable',eur(v.pay)),
    v.carried?null:cell('Dispute by',v.by||'n/a')));
  (v.warn||[]).forEach(function(w){inner.append(h('div',{class:'warn',role:'status'},fmt(w)))});
  if(d&&d.d!=='confirmed'){var dl=h('dl',{class:'decided '+(PILL[st(v)]||'')});
    function row(k,x){if(x)dl.append(h('dt',{},k),h('dd',{},x))}
    row('Amount',['letter_ok','disagree','not_ours','dispute','change'].indexOf(d.d)>=0&&d.amount?eur(d.amount)+' excl.':'');
    row('Reason',d.reason);
    row('Proposal',(d.overrule||v.proposal_ex!==v.ex)&&v.verdict?VERB[v.verdict]+(isZero(v.proposal_ex)?'':', '+eur(v.proposal_ex)+' excl.'):'');
    if(dl.children.length)inner.append(dl)}
  {
    var avail=SECS.filter(function(s){return s[0]==='wo'?!!v.wo_rec:!v.carried&&(s[0]==='findings'||(s[0]==='letter'&&v.letter)||(s[0]==='previous'&&v.previous)||(s[0]==='raw'&&v.raw)||(s[0]==='en'&&v.en))});
    var allOpen=avail.every(function(s){return UI.open[s[0]]});
    if(avail.length>1)inner.append(h('div',{class:'toolbar'},btn('btn',allOpen?'chevrons-down-up':'chevrons-up-down',allOpen?'Collapse all':'Expand all',function(){
      avail.forEach(function(s){UI.open[s[0]]=!allOpen});saveUI();renderDetail()})));
    avail.forEach(function(s){var k=s[0],o=!!UI.open[k],b=h('div',{class:'sec-b'},sectionBody(k,v));b.hidden=!o;
      var head=h('button',{class:'sec-h',type:'button','aria-expanded':String(o),onclick:function(){
        UI.open[k]=!UI.open[k];saveUI();head.setAttribute('aria-expanded',String(UI.open[k]));b.hidden=!UI.open[k];
        var ta=b.querySelector('textarea');if(ta&&UI.open[k])fit(ta);}},
        s[1],k==='wo'?h('span',{class:'n'},v.wo_rec.id):k==='findings'?h('span',{class:'n'},String(v.findings.length)):k==='previous'?h('span',{class:'n'},v.previous.invoice):null,h('span',{class:'ch'},ic('chevron-down')));
      inner.append(h('section',{class:'sec',id:'sec-'+k},head,b))});
  }
  box.append(inner);
  var ta=box.querySelector('textarea.letter');if(ta&&UI.open.letter)fit(ta);
  box.scrollTop=keepTop;
}

// ---- needs attention
function initAttention(){
  var dlg=$('attention');
  $('attn').addEventListener('click',function(){
    var box=$('attn-list');clear(box);
    (D.needs_attention||[]).forEach(function(a){
      var v=byId[a.invoice],can=!!v||(LIVE&&a.month);
      box.append(h('button',{class:'att',type:'button',disabled:can?null:'disabled',onclick:function(){dlg.close();goTo(a.invoice,a.month)}},
        h('b',{},a.invoice),h('span',{class:'m'},a.month),
        h('span',{},(a.update==='correction_received'?'Replaced by ':'Credit note ')+a.linked_invoice+' ('+a.arrived+')')))});
    dlg.showModal()});
  $('close-attention').addEventListener('click',function(){dlg.close()})}

// ---- settings
function initSettings(){
  var dlg=$('settings'),text=['greeting','closing','signer','dept'],all=dlg.querySelectorAll('input'),save=$('save-settings'),err=$('s-err');
  function fill(){$('s-small').value=dsep(S.small_threshold_excl_vat);$('s-repeat').value=S.repeat_threshold;
    text.forEach(function(f){$('s-'+f).value=S[f]||''});
    Array.prototype.forEach.call(document.querySelectorAll('input[name=num]'),function(r){r.checked=r.value===S.num});err.textContent=''}
  if(!LIVE){Array.prototype.forEach.call(all,function(i){i.disabled=true});save.disabled=true;$('s-off').hidden=false}
  $('open-settings').addEventListener('click',function(){fill();dlg.showModal()});
  $('close-settings').addEventListener('click',function(){dlg.close()});
  save.addEventListener('click',function(){
    var body={small_threshold_excl_vat:undsep($('s-small').value),repeat_threshold:$('s-repeat').value.trim(),month:D.live.month};
    text.forEach(function(f){body[f]=$('s-'+f).value});
    var r=document.querySelector('input[name=num]:checked');if(r)body.num=r.value;
    err.textContent='';save.disabled=true;
    api('/api/settings',body).then(function(j){save.disabled=false;adopt(j.data);dlg.close();keepSel();renderAll()},
      function(e){save.disabled=false;err.textContent=e.message})})}

// ---- boot
$('q').addEventListener('input',function(e){query=e.target.value.trim().toLowerCase();keepSel();renderTabs();renderList();renderDetail()});
document.addEventListener('keydown',function(e){
  var t=e.target&&e.target.tagName;if(t==='INPUT'||t==='TEXTAREA'||t==='SELECT'||e.ctrlKey||e.metaKey||e.altKey||document.querySelector('dialog[open]'))return;
  if(e.key==='j')step(1);else if(e.key==='k')step(-1)});
var want=new URLSearchParams(location.search).get('invoice');
if(!want){var hm=/^#invoice=(.+)$/.exec(location.hash);if(hm){try{want=decodeURIComponent(hm[1])}catch(e){}}}
if(want&&byId[want]){UI.sel=want;UI.filter='all'}else want=null;
if(!byId[UI.sel])UI.sel=items().length?items()[0].id:null;
initSettings();initAttention();initQueue();
if(LIVE){
  if(D.live.months.length>1){var mp=h('select',{class:'mpick','aria-label':'Month',onchange:function(){location.href='/?month='+encodeURIComponent(mp.value)}},
      D.live.months.map(function(m){return h('option',{value:m},m==='all'?'All months':m)}));
    mp.value=D.live.month;$('open-settings').before(mp)}
  setInterval(function(){fetch('/api/ping',{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json()}).then(function(j){
    if(!j.ok)throw 0;if(DEAD){DEAD=false;$('closed').hidden=true;renderDetail()}}).catch(markDead)},10000);
}
if(window.innerWidth>820||want){setView('detail')}else setView('list');
keepSel();renderAll();
if(want){$('detail').scrollIntoView({block:'start'});
  try{var q2=new URLSearchParams(location.search);q2.delete('invoice');history.replaceState(null,'',location.pathname+(q2.toString()?'?'+q2:''))}catch(e){}}
})();
"""

SETTINGS_HTML = """<dialog id="settings" aria-labelledby="s-title"><div class="dlg-h"><h2 id="s-title">Settings</h2>
<button type="button" class="btn icon" id="close-settings" aria-label="Close"><svg class="i" aria-hidden="true"><use href="#i-x"/></svg></button></div>
<div class="dlg-b"><fieldset><legend>Thresholds</legend><label>Small threshold (EUR excl. VAT)<input type="text" inputmode="decimal" id="s-small"></label>
<label>Repeat count<input type="text" inputmode="numeric" id="s-repeat"></label></fieldset>
<fieldset><legend>Letters</legend><label>Greeting<input type="text" id="s-greeting"></label><label>Closing<input type="text" id="s-closing"></label>
<label>Signer name<input type="text" id="s-signer"></label><label>Department<input type="text" id="s-dept"></label></fieldset>
<fieldset><legend>Number format</legend><div class="seg" role="radiogroup" aria-label="Number format"><label><input type="radio" name="num" value="nl">1.234,56</label>
<label><input type="radio" name="num" value="en">1,234.56</label></div></fieldset></div>
<div class="dlg-f"><span class="muted" id="s-off" hidden>Settings can only be changed in the live dashboard.</span><span class="err" id="s-err" role="alert" style="margin:0"></span>
<button type="button" class="btn primary" id="save-settings">Save</button></div></dialog>
<dialog id="attention" aria-labelledby="a-title"><div class="dlg-h"><h2 id="a-title">Needs attention</h2>
<button type="button" class="btn icon" id="close-attention" aria-label="Close"><svg class="i" aria-hidden="true"><use href="#i-x"/></svg></button></div>
<div class="dlg-b" id="attn-list"></div></dialog>"""


def esc(x) -> str:
    return escape("" if x is None else str(x), quote=True)


def money(x) -> str:
    """Plain decimal string with two places; anything unparseable is passed through."""
    try:
        return f"{Decimal(str(x)):.2f}"
    except (InvalidOperation, ValueError):
        return str(x or "")


def letter_parts(text: str, s: dict | None = None) -> dict:
    """Split a server.letter() text into head, body and the parts the settings panel can change."""
    greeting, closing = (s or DEFAULTS)["greeting"], (s or DEFAULTS)["closing"]
    lines = text.split("\n")
    try:
        g, c = lines.index(greeting), len(lines) - 1 - lines[::-1].index(closing)
    except ValueError:
        return {"head": "", "body": text.rstrip("\n"), "plain": True}
    return {"head": "\n".join(lines[:g - 1]), "body": "\n".join(lines[g + 2:c - 1])}


def finding_json(f, m: dict) -> dict:
    return {"rule": f.rule, "plain": m.get("plain") or f.issue, "refs": m.get("refs") or [], "inv": m.get("invoice_quote") or "",
            "ex": money(f.disputed_excl_vat), "in": money(f.disputed_incl_vat),
            "small": bool(m.get("small", f.small)), "repeat": bool(m.get("repeat", f.repeat)),
            "repeat_count": m.get("repeat_count", f.repeat_count), "hold": bool(f.hold), "provisional": bool(f.provisional)}


def decision_json(r, dec: dict | None) -> dict | None:
    if not dec:
        return None
    d = dec["decision"]
    amount = money(dec["amount_excl_vat"]) if dec.get("amount_excl_vat") and d not in ("approve", "pay", "let_go") else ""
    return {"d": d, "date": (dec.get("timestamp") or "")[:10], "amount": amount, "reason": dec.get("reason") or "",
            "amount_incl": money(dec["amount_incl_vat"]) if dec.get("amount_incl_vat") else "",
            "overrule": dec.get("overrule") == "yes"}


def effective_amounts(r, dec: dict | None) -> tuple[str, str]:
    """Disputed (excl, incl) VAT: Sanne's amount once she has set one, else the proposal."""
    ex, inc = money(r.total_disputed_excl_vat), money(r.total_disputed_incl_vat)
    if dec and dec.get("decision") not in ("hold", "undo") and dec.get("amount_excl_vat") not in (None, "")             and dec["decision"] not in ("approve", "pay", "let_go"):
        ex = money(dec["amount_excl_vat"])
        if dec.get("amount_incl_vat") not in (None, ""):
            inc = money(dec["amount_incl_vat"])
    return ex, inc


def invoice_json(r, im: dict, dec: dict | None, overrules: dict, live: bool, s: dict) -> dict:
    fm = im.get("findings", [])
    letter = None
    if im.get("letter_nl"):
        letter = letter_parts(im["letter_nl"], s)
        if live:
            letter["saved"] = im["letter_nl"]
    warn = [f"{n} overrules for {r.contractor} on {k}: review this rule with the team."
            for k in dict.fromkeys(f.rule for f in r.findings) if (n := overrules.get(f"{r.contractor}|{k}", 0)) >= 3]
    raw = im.get("raw") or ""
    ex, inc = effective_amounts(r, dec)
    addr = re.search(r"^Locatie:\s*(.+?)\s*$", raw, re.M)
    return {"id": r.invoice, "contractor": r.contractor, "number": r.number, "wo": r.wo, "date": im.get("date") or "",
            "addr": addr.group(1) if addr else "", "exec": im.get("exec") or "", "wo_rec": plain(im.get("wo_rec")),
            "risk": r.risk, "verdict": r.verdict, "proposal": im.get("proposal") or r.verdict,
            "status": im.get("status") or "open", "days_waiting": im.get("days_waiting"),
            "sent_date": im.get("sent_date") or "", "resolved_kind": im.get("resolved_kind") or "",
            "linked_invoice": im.get("linked_invoice") or "", "link": plain(im.get("link")), "update": plain(im.get("update")),
            "small": bool(im.get("small")), "repeat": bool(im.get("repeat")), "actions": list(im.get("actions") or []),
            "ex": ex, "inc": inc, "proposal_ex": money(r.total_disputed_excl_vat), "pay": money(r.payable_incl_vat),
            "total": money(im.get("total", "0")), "by": str(r.dispute_by) if r.dispute_by else "",
            "findings": [finding_json(f, fm[i] if i < len(fm) else {}) for i, f in enumerate(r.findings)],
            "readings": im.get("readings") or [], "reading": im.get("reading") or "",
            "letter": letter, "en": im.get("letter_en") or "", "raw": raw, "decision": decision_json(r, dec),
            "warn": warn, "previous": plain(im.get("previous"))}


def error_json(e: dict) -> dict:
    return {"id": str(e["file"]), "contractor": "Could not be read", "number": "", "wo": "", "date": "", "addr": "",
            "risk": "high", "verdict": "hold", "proposal": "hold", "status": "open", "days_waiting": None, "sent_date": "",
            "resolved_kind": "", "linked_invoice": "", "link": None, "update": None, "small": False, "repeat": False,
            "exec": "", "wo_rec": None, "actions": [], "ex": "0.00", "inc": "0.00", "pay": "0.00", "total": "0.00", "by": "", "err": True,
            "findings": [{"plain": str(e["error"]), "refs": [], "inv": "", "ex": "0.00", "in": "0.00", "small": False,
                          "repeat": False, "repeat_count": 0, "hold": True, "provisional": False}],
            "readings": [], "reading": "", "letter": None, "en": "", "raw": "", "decision": None, "warn": [], "previous": None}


def plain(x):
    """JSON-safe copy: Decimals from the server become strings like "90.40"."""
    return json.loads(json.dumps(x, default=str))


def build_data(results, decisions, meta, live=None) -> dict:
    dec = {row["invoice"]: row for row in decisions}  # last row per invoice wins
    inv = meta.get("invoices", {})
    settings = {**DEFAULTS, **(meta.get("settings") or {})}
    order = sorted(results, key=lambda r: (RISKS.index(r.risk), VERDICTS.index(r.verdict), r.invoice))
    items = [invoice_json(r, inv.get(r.invoice, {}), dec.get(r.invoice), meta.get("overrules", {}), bool(live), settings)
             for r in order]
    items = [x for x in items if x["risk"] == "high"] + [x for x in items if x["risk"] == "medium"] \
        + [x for x in items if x["risk"] == "low"]
    errs = [error_json(e) for e in meta.get("errors", [])]
    out = {"run": str(meta.get("run") or ""), "month": str(meta.get("month") or ""),
           "defaults": {k: settings[k] for k in DEFAULTS}, "settings": settings,
           "status_counts": meta.get("status_counts") or {},
           "total_ex": money(sum((Decimal(x["ex"]) for x in items), Decimal(0))),
           "total_in": money(sum((Decimal(x["inc"]) for x in items), Decimal(0))),
           "invoices": errs + items, "carried": plain(meta.get("carried") or []),
           "needs_attention": plain(meta.get("needs_attention") or [])}
    if live:
        out["live"] = live
    return out


def icon_sprite() -> str:
    syms = "".join(f'<symbol id="i-{k}" viewBox="0 0 24 24">{v}</symbol>' for k, v in ICONS.items())
    return f'<svg width="0" height="0" style="position:absolute" aria-hidden="true">{syms}</svg>'


def render(results, decisions, meta, live=None) -> str:
    """live: {token, month, months} when served by the MCP server; None for the read-only file snapshot."""
    data = json.dumps(build_data(results, decisions, meta, live), ensure_ascii=False).replace("<", "\\u003c")
    month, run = esc(meta.get("month")), esc(meta.get("run"))
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Invoice review {month}</title><style>{CSS}</style></head><body>{icon_sprite()}"
        '<div class="app"><header class="top"><div class="top-row">'
        f'<h1>Invoice review {month}</h1><span class="run">{run}</span><span class="chip">Proposals only</span><span class="sp"></span>'
        '<button type="button" class="btn attn" id="attn" hidden><span>Needs attention</span><b id="attn-n"></b></button>'
        '<button type="button" class="btn" id="open-settings"><svg class="i" aria-hidden="true"><use href="#i-settings-2"/></svg>'
        "<span>Settings</span></button></div>"
        '<div class="closed" id="closed" role="alert" hidden>Dashboard closed. Open Claude to continue.</div>'
        '<div class="kpis" id="kpis"></div></header>'
        '<div class="panes"><aside class="queue"><div class="q-head"><label class="search">'
        '<svg class="i" aria-hidden="true"><use href="#i-search"/></svg>'
        '<input id="q" type="search" placeholder="Search" aria-label="Search invoice, contractor or work order"></label>'
        '<div class="tabs" id="tabs" role="group" aria-label="Status"></div>'
        '<div class="ctl"><div class="fwrap"><button type="button" class="btn" id="flt-btn" aria-expanded="false" aria-controls="flt-pop">'
        '<svg class="i" aria-hidden="true"><use href="#i-sliders-horizontal"/></svg><span>Filter</span><b id="flt-n" hidden></b></button>'
        '<div class="fpop" id="flt-pop" role="group" aria-label="Filter" hidden></div></div>'
        '<label class="sortw"><span>Sort</span><select id="sort"></select></label><span class="sp"></span>'
        '<button type="button" class="btn quiet" id="clear" hidden>Clear</button></div>'
        '<div class="chips" id="chips" hidden></div></div><ul class="list" id="list"></ul></aside>'
        f'<main class="detail" id="detail"></main></div></div>{SETTINGS_HTML}'
        f'<script type="application/json" id="data">{data}</script><script>{JS}</script></body></html>'
    )
