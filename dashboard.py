"""Local dashboard server: serves review.html on 127.0.0.1 and records Sanne's clicks through server.py.

Stdlib only. It runs in a daemon thread inside the MCP server process. stdout is the MCP channel, so log to stderr.
Trust boundary: every request needs a local Host header, every POST needs the per-process token and a same-origin
Origin (if sent). Request data never forms a file path: the folder is fixed by the process, letter paths come
from invoice ids that exist in the current run.
"""
import json
import secrets
import sys
import threading
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

import report

PORTS = range(8765, 8776)
MAX_BODY = 200_000
MAX_REASON = 500
MAX_LETTER = 20_000
VERDICTS = ("approve", "dispute", "hold")
ACTIONS = ("pay", "letter_ok", "sent", "hold", "confirmed", "not_ours", "disagree", "resolved", "let_go", "undo")
DECISIONS = ACTIONS + ("approve", "dispute", "change")  # old names kept as aliases
MAX_FIELD = 40
CSP = ("default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; "
       "img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


class Bad(Exception):
    def __init__(self, msg: str, status: int = 400):
        super().__init__(msg)
        self.status = status


class Httpd(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows this would let a second process bind the same port


def parse_amount(x) -> Decimal | None:
    if x in (None, ""):
        return None
    if isinstance(x, bool) or not isinstance(x, (str, int, float)):
        raise Bad("The amount is not a number.")
    try:
        d = Decimal(str(x).strip())
    except InvalidOperation:
        raise Bad("The amount is not a number.")
    if not d.is_finite() or d < 0:
        raise Bad("The amount must be zero or more.")
    if d.as_tuple().exponent < -2:
        raise Bad("The amount can have at most 2 decimals.")
    return d


class Dashboard:
    def __init__(self, core, ports=PORTS):
        self.core, self.ports = core, tuple(ports)
        self.token = secrets.token_urlsafe(32)
        self.httpd = None
        self.port = None
        self.folder = None
        self.month = None
        self.lock = threading.RLock()

    # ---- lifecycle
    def serve(self, folder, month=None) -> str:
        """Point the dashboard at a folder (starting the server on first use) and return its URL."""
        with self.lock:
            opts = self.core.month_options(folder)
            if month is not None and month not in opts:
                raise ValueError(f"unknown month {month!r}; choose one of {', '.join(opts) or 'none'}")
            self.folder = folder
            self.month = month or ("all" if "all" in opts else opts[-1])
            if self.httpd is None:
                self._bind()
            return f"http://127.0.0.1:{self.port}/?month={self.month}"

    def _bind(self):
        for p in self.ports:
            try:
                httpd = Httpd(("127.0.0.1", p), Handler)
            except OSError:
                continue
            httpd.dash = self
            self.httpd, self.port = httpd, httpd.server_address[1]
            threading.Thread(target=httpd.serve_forever, daemon=True, name="dashboard").start()
            print(f"dashboard: listening on 127.0.0.1:{self.port}", file=sys.stderr)
            return
        raise OSError(f"No free port for the dashboard (tried {self.ports[0]} to {self.ports[-1]}). "
                      "Close other programs or other Claude sessions that use them, then try again.")

    def stop(self):
        with self.lock:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()
                self.httpd = self.port = None

    # ---- work, always from disk
    def month_key(self, asked, opts) -> str:
        if asked is None:
            return self.month if self.month in opts else ("all" if "all" in opts else opts[-1])
        if asked not in opts:
            raise Bad("Unknown month.")
        return asked

    def live(self, month, opts) -> dict:
        return {"token": self.token, "month": month, "months": opts}

    def page(self, asked):
        with self.lock:
            opts = self.core.month_options(self.folder)
            month = self.month = self.month_key(asked, opts)
            data = self.core.refresh(self.folder, None if month == "all" else month)
            return report.render(*data, live=self.live(month, opts)).encode("utf-8")

    def invoice_ids(self, m):
        return {r.invoice for r in self.core.run_checks(self.folder, m)[1]}

    @staticmethod
    def field(body: dict, key: str):
        v = body.get(key)
        if v is not None and (not isinstance(v, str) or len(v) > MAX_FIELD):
            raise Bad(f"The {key} is not valid.")
        return v or None

    def decision(self, body: dict) -> dict:
        with self.lock:
            core, d = self.core, self.folder
            opts = core.month_options(d)
            month = self.month_key(body.get("month"), opts)
            m = None if month == "all" else month
            inv, dec, reason = body.get("invoice"), body.get("decision"), body.get("reason", "")
            if not isinstance(inv, str) or inv not in core.decidable_ids(d, m):
                raise Bad("That invoice is not in this run.")
            if dec not in DECISIONS:
                raise Bad("Unknown decision. Use one of: " + ", ".join(ACTIONS) + ".")
            if not isinstance(reason, str) or len(reason) > MAX_REASON:
                raise Bad(f"The reason can have at most {MAX_REASON} characters.")
            amount = parse_amount(body.get("amount"))
            verdict, kind = self.field(body, "verdict"), self.field(body, "kind")
            sent, linked = self.field(body, "date"), self.field(body, "linked_invoice")
            if dec in ("change", "disagree"):
                if verdict not in VERDICTS:
                    raise Bad("Choose a verdict for the change.")
                if not reason.strip():
                    raise Bad("A reason is required to change a proposal.")
                if verdict != "dispute":
                    amount = None
            elif dec not in ("letter_ok", "dispute"):
                amount = None
            try:
                row, r, rule_ids, note = core.append_decision(d, inv, dec, reason, amount, verdict=verdict, kind=kind,
                                                              sent_date=sent, linked_invoice=linked)
                page = core.refresh(d, m, {inv})
            except ValueError as e:
                raise Bad(str(e))
            except TimeoutError as e:
                raise Bad(str(e), 503)
            counts, warnings = core.overrule_summary(d, r, rule_ids, note)
            data = report.build_data(*page, live=self.live(month, opts))
            return {"ok": True, "row": row, "warnings": warnings, "data": data}

    def settings(self, body: dict) -> dict:
        """Save letter and threshold settings; unsent letters of this month are recomposed with them."""
        with self.lock:
            core, d = self.core, self.folder
            opts = core.month_options(d)
            month = self.month_key(body.get("month"), opts)
            m = None if month == "all" else month
            try:
                saved = core.save_settings(d, {k: v for k, v in body.items() if k != "month"})
                page = core.refresh(d, m, set(self.invoice_ids(m)))
            except ValueError as e:
                raise Bad(str(e))
            return {"ok": True, "settings": saved, "data": report.build_data(*page, live=self.live(month, opts))}

    def letter(self, body: dict) -> dict:
        with self.lock:
            opts = self.core.month_options(self.folder)
            month = self.month_key(body.get("month"), opts)
            m = None if month == "all" else month
            inv, text = body.get("invoice"), body.get("text")
            if not isinstance(inv, str) or inv not in self.invoice_ids(m):
                raise Bad("That invoice is not in this run.")
            if not isinstance(text, str) or not text.strip() or len(text) > MAX_LETTER:
                raise Bad(f"The letter must have text and at most {MAX_LETTER} characters.")
            try:
                path = self.core.save_letter(self.folder, m, inv, text)
            except ValueError as e:
                raise Bad(str(e))
            return {"ok": True, "file": path}


class Handler(BaseHTTPRequestHandler):
    server_version = "InvoiceCheck"

    def log_message(self, fmt, *args):
        print("dashboard: " + fmt % args, file=sys.stderr)

    def send(self, status: int, body: bytes, ctype: str):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, status: int, obj):
        self.send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def guard(self, post: bool):
        dash = self.server.dash
        local = (f"127.0.0.1:{dash.port}", f"localhost:{dash.port}")
        if self.headers.get("Host") not in local:
            raise Bad("Forbidden.", 403)
        if post:
            origin = self.headers.get("Origin")
            if origin is not None and origin not in tuple("http://" + h for h in local):
                raise Bad("Forbidden.", 403)
            if not secrets.compare_digest(self.headers.get("X-Token", "").encode(), dash.token.encode()):
                raise Bad("Forbidden.", 403)

    def body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise Bad("Bad request.")
        if n <= 0 or n > MAX_BODY:
            raise Bad("Bad request.", 413 if n > MAX_BODY else 400)
        try:
            obj = json.loads(self.raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise Bad("Bad request.")
        if not isinstance(obj, dict):
            raise Bad("Bad request.")
        return obj

    def handle_one(self, post: bool):
        dash = self.server.dash
        # Read the request body before any reply, so an early 400/403 never closes the socket on unread data
        # (that resets the connection and the client sees ConnectionAbortedError instead of the status).
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            n = 0
        self.raw = self.rfile.read(n) if post and 0 < n <= MAX_BODY else b""
        try:
            self.guard(post)
            url = urlsplit(self.path)
            if not post and url.path == "/":
                asked = parse_qs(url.query).get("month", [None])[0]
                self.send(200, dash.page(asked), "text/html; charset=utf-8")
            elif not post and url.path == "/api/ping":
                self.send_json(200, {"ok": True})
            elif post and url.path == "/api/decision":
                self.send_json(200, dash.decision(self.body()))
            elif post and url.path == "/api/settings":
                self.send_json(200, dash.settings(self.body()))
            elif post and url.path == "/api/letter":
                self.send_json(200, dash.letter(self.body()))
            else:
                raise Bad("Not found.", 404)
        except Bad as e:
            self.send_json(e.status, {"error": str(e)})
        except Exception as e:  # never leak a traceback to the page
            print(f"dashboard: error {type(e).__name__}: {e}", file=sys.stderr)
            self.send_json(500, {"error": "Something went wrong. Check the decisions file before trying again."})

    def do_GET(self):
        self.handle_one(False)

    def do_POST(self):
        self.handle_one(True)
