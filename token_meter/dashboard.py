"""Self-contained HTML dashboard (no external scripts, works offline) and a live server."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .analysis import by_model, model_switches
from .forecast import forecast
from .i18n import get_lang, t

TEMPLATE = Path(__file__).with_name("dashboard.html")


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o).__name__)


def to_json(obj) -> str:
    # '<' escaped so nothing inside the data can close the <script> tag
    return json.dumps(obj, default=_json_default, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")


def payload(res, records, unknown, window: int, now: datetime, live: bool = False) -> dict:
    """Everything the page needs, pre-aggregated per day so the page can filter by date."""
    meta = {
        "version": __version__, "lang": get_lang(), "generated": now, "live": live,
        "files": res.files, "duplicates": res.duplicates, "roots": res.roots,
        "unknown_models": sorted(unknown), "window": window,
    }
    if not records:
        return {"meta": meta, "days": [], "models": [], "forecast": None}

    first_day = records[0].ts.date()
    last_day = max(records[-1].ts.date(), now.date())
    n = (last_day - first_day).days + 1
    days = [(first_day + timedelta(days=i)).isoformat() for i in range(n)]

    models = by_model(records)
    cells = {m["model"]: {k: [0] * n for k in ("in", "out", "cw", "cr", "cost", "req")} for m in models}
    hours = [[0] * 24 for _ in range(n)]
    projects, sessions = {}, {}

    for r in records:
        i = (r.ts.date() - first_day).days
        c = cells[r.model]
        c["in"][i] += r.input
        c["out"][i] += r.output
        c["cw"][i] += r.cache_write
        c["cr"][i] += r.cache_read
        c["cost"][i] += r.cost
        c["req"][i] += 1
        hours[i][r.ts.hour] += r.total

        p = projects.setdefault(r.project or "?", {"name": r.project or "?", "days": {}, "sessions": set()})
        p["sessions"].add(r.session)
        d = p["days"].setdefault(i, [0, 0.0, 0])
        d[0] += r.total; d[1] += r.cost; d[2] += 1

        s = sessions.get(r.session)
        if s is None:
            s = sessions[r.session] = {"id": r.session, "project": r.project, "first": r.ts,
                                       "last": r.ts, "models": {}, "days": {}}
        s["last"] = r.ts
        s["models"][r.model] = s["models"].get(r.model, 0) + r.total
        d = s["days"].setdefault(i, [0, 0.0, 0])
        d[0] += r.total; d[1] += r.cost; d[2] += 1

    for c in cells.values():
        c["cost"] = [round(x, 4) for x in c["cost"]]

    def sparse(dd):
        return [[i, v[0], round(v[1], 4), v[2]] for i, v in sorted(dd.items())]

    return {
        "meta": meta,
        "days": days,
        "models": [{"model": m["model"], "first": m["first"], "last": m["last"],
                    "days_used": m["days_used"]} for m in models],
        "cells": cells,
        "hours": hours,
        "switches": model_switches(records),
        "projects": [{"name": p["name"], "sessions": len(p["sessions"]), "days": sparse(p["days"])}
                     for p in projects.values()],
        "sessions": [{"id": s["id"], "project": s["project"], "first": s["first"], "last": s["last"],
                      "models": sorted(s["models"], key=s["models"].get, reverse=True),
                      "days": sparse(s["days"])} for s in sessions.values()],
        "forecast": forecast(records, now, window),
    }


def render_html(data: dict) -> str:
    html = TEMPLATE.read_text(encoding="utf-8")
    return html.replace("__LANG__", data["meta"]["lang"]).replace("/*__DATA__*/null", to_json(data))


def write(path, data: dict) -> Path:
    out = Path(path).resolve()
    out.write_text(render_html(data), encoding="utf-8")
    return out


def serve(args, collect) -> int:
    """Serve the dashboard on localhost; data is re-read at most every 30 seconds."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    lock = threading.Lock()
    cache = {"at": 0.0, "data": None}

    def current():
        with lock:
            if cache["data"] is None or time.time() - cache["at"] > 30:
                res, records, unknown = collect(args)
                cache["data"] = payload(res, records, unknown, args.window,
                                        datetime.now().astimezone(), live=True)
                cache["at"] = time.time()
            return cache["data"]

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - http.server naming
            route = self.path.split("?", 1)[0]
            if route in ("/", "/index.html"):
                body, ctype = render_html(current()).encode("utf-8"), "text/html; charset=utf-8"
            elif route == "/api/data":
                body, ctype = to_json(current()).encode("utf-8"), "application/json; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{httpd.server_address[1]}/"
    print(t("serving", url=url), flush=True)
    if not args.no_open:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
