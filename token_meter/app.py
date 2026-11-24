"""Desktop app: a small window that runs the live dashboard in the background.

``token-meter-app`` (or the packaged Claude Token Meter app) starts the dashboard
server, opens the dashboard in its own window and shows today's numbers.
Closing the window stops the server.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

from . import __version__, report
from .cli import build_parser, collect
from .dashboard import APP_ID, make_server
from .i18n import STRINGS, get_lang, set_lang, t

PORT = 8765
ICON = Path(__file__).with_name("icon.png")
REFRESH_MS = 60_000
# never send requests to our own localhost server through a system proxy
_http = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def settings_file() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home()) / "ClaudeTokenMeter" / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ClaudeTokenMeter" / "settings.json"
    base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return base / "claude-token-meter" / "settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(settings_file().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    path = settings_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def _get(url: str, timeout: float = 60) -> bytes:
    with _http.open(url, timeout=timeout) as resp:
        return resp.read()


def running_at(url: str) -> bool:
    """True if another Claude Token Meter already answers at this address."""
    try:
        return json.loads(_get(url + "api/ping", timeout=2)).get("app") == APP_ID
    except (OSError, ValueError, AttributeError):
        return False


def server_args(paths):
    argv = ["serve", "--no-open"]
    for p in paths or []:
        argv += ["--path", p]
    return build_parser().parse_args(argv)


def start_server(args):
    """Bind port 8765, or a free port if something else holds it.

    Returns (httpd, url); httpd is None when Token Meter is already running there.
    """
    try:
        return make_server(args, collect, PORT)
    except OSError:
        pass
    url = f"http://127.0.0.1:{PORT}/"
    if running_at(url):
        return None, url
    return make_server(args, collect, 0)


def edge_path():
    if os.name != "nt":
        return None
    for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
        base = os.environ.get(var)
        exe = Path(base, "Microsoft", "Edge", "Application", "msedge.exe") if base else None
        if exe and exe.is_file():
            return str(exe)
    return shutil.which("msedge")


def open_dashboard(url: str, app_window: bool = True) -> None:
    """Open the dashboard in an app-style Edge window on Windows, else the default browser."""
    edge = edge_path() if app_window else None
    if edge:
        try:
            subprocess.Popen([edge, f"--app={url}"])
            return
        except OSError:
            pass
    webbrowser.open(url)


def summarize(data: dict, now: datetime = None):
    """The four numbers shown in the window as (value, detail) strings, or None without data."""
    fc = data.get("forecast")
    if not fc:
        return None
    days = data.get("days") or []
    today = (now or datetime.now().astimezone()).date().isoformat()
    tokens = cost = requests = 0
    if today in days:
        i = days.index(today)
        for c in data["cells"].values():
            tokens += c["in"][i] + c["out"][i] + c["cw"][i] + c["cr"][i]
            cost += c["cost"][i]
            requests += c["req"][i]
    rate = fc["rate"]["per_day"]
    h30 = fc["horizons"]["30d"]
    block = fc["current_block"]
    return {
        "today": (report.num(tokens), f"{report.usd(cost)} · {t('app_req', n=requests)}"),
        "rate": (report.num(rate["total"]) + t("per_day"), report.usd(rate["cost"]) + t("per_day")),
        "next30": (report.num(h30["tokens"]), report.usd(h30["cost"])),
        "block": ((report.num(block["total"]),
                   f"{t('app_block_left', left=report.duration(block['remaining_min']))} · {report.usd(block['cost'])}")
                  if block else ("—", t("app_block_none"))),
    }


def self_test(args) -> int:
    """Start the server on a free port, fetch the page and the data. Exit 0 if all is well."""
    try:
        import tkinter
        tk_version = tkinter.Tcl().eval("info patchlevel")
    except Exception as exc:  # noqa: BLE001 - report whatever broke
        print(f"self-test: FAIL tkinter: {exc!r}")
        return 2
    try:
        httpd, url = make_server(args, collect, 0)
    except OSError as exc:
        print(f"self-test: FAIL server: {exc}")
        return 1
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        page = _get(url).decode("utf-8")
        data = json.loads(_get(url + "api/data?refresh=1"))
        ok = "<html" in page.lower() and "meta" in data and running_at(url)
    except Exception as exc:  # noqa: BLE001
        print(f"self-test: FAIL request: {exc!r}")
        return 1
    finally:
        httpd.shutdown()
        httpd.server_close()
    print(f"self-test: {'OK' if ok else 'FAIL'} version={__version__} tk={tk_version} "
          f"files={data['meta']['files']} models={len(data.get('models') or [])}")
    return 0 if ok else 1


def run_headless(httpd, url: str, open_page: bool) -> int:
    print(t("serving", url=url), flush=True)
    if open_page:
        open_dashboard(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0


class App:
    CARDS = ("today", "rate", "next30", "block")

    def __init__(self, tk, httpd, url: str, window: int):
        from tkinter import font, ttk

        self.tk, self.httpd, self.url, self.window = tk, httpd, url, window
        self.results = queue.Queue()
        self.loading = False
        self.data = None

        if os.name == "nt":
            try:  # sharp text on high-DPI screens
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except (AttributeError, OSError):
                pass
        self.root = root = tk.Tk()
        root.title("Claude Token Meter")
        root.resizable(False, False)
        try:
            self.icon = tk.PhotoImage(file=str(ICON))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            pass
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if sys.platform == "darwin":
            root.createcommand("::tk::mac::Quit", self.quit)

        base = font.nametofont("TkDefaultFont")
        family, size = base.actual("family"), abs(base.actual("size")) or 10
        big = font.Font(family=family, size=size + 6, weight="bold")
        title = font.Font(family=family, size=size + 4, weight="bold")
        link = font.Font(family=family, size=size, underline=True)

        frame = ttk.Frame(root, padding=16)
        frame.grid(sticky="nsew")
        head = ttk.Frame(frame)
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(head, text="Claude Token Meter", font=title).pack(side="left")
        ttk.Label(head, text=f"v{__version__}", foreground="#6b7280").pack(side="left", padx=(8, 0), pady=(4, 0))
        self.url_label = ttk.Label(frame, foreground="#2563eb", cursor="hand2", font=link)
        self.url_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 12))
        self.url_label.bind("<Button-1>", lambda _e: webbrowser.open(self.url))

        self.cards = {}
        for k, key in enumerate(self.CARDS):
            box = ttk.LabelFrame(frame, padding=(12, 6, 12, 10))
            box.grid(row=2 + k // 2, column=k % 2, sticky="nsew", padx=(0 if k % 2 == 0 else 6, 0), pady=(0, 6))
            value = ttk.Label(box, text="…", font=big)
            value.pack(anchor="w")
            detail = ttk.Label(box, text=" ", foreground="#6b7280")
            detail.pack(anchor="w")
            self.cards[key] = (box, value, detail)
        frame.columnconfigure(0, weight=1, uniform="card", minsize=210)
        frame.columnconfigure(1, weight=1, uniform="card", minsize=210)

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self.b_open = ttk.Button(buttons, command=lambda: open_dashboard(self.url))
        self.b_browser = ttk.Button(buttons, command=lambda: webbrowser.open(self.url))
        self.b_refresh = ttk.Button(buttons, command=lambda: self.load(force=True))
        for b in (self.b_open, self.b_browser, self.b_refresh):
            b.pack(side="left", padx=(0, 6))
        self.b_quit = ttk.Button(buttons, command=self.quit)
        self.b_quit.pack(side="right")
        self.b_lang = ttk.Button(buttons, command=self.toggle_lang)
        self.b_lang.pack(side="right", padx=(0, 6))

        self.status = ttk.Label(frame, foreground="#6b7280")
        self.status.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.note = ttk.Label(frame, foreground="#6b7280")
        self.note.grid(row=6, column=0, columnspan=2, sticky="w")
        self.b_open.focus_set()
        root.bind("<Return>", lambda _e: open_dashboard(self.url))

        self.texts()
        self.load()
        root.after(150, self.poll)
        root.after(REFRESH_MS, self.tick)

    def texts(self) -> None:
        captions = {"today": t("app_today"), "rate": t("app_rate", w=self.window),
                    "next30": t("app_next30"), "block": t("app_block")}
        for key, (box, _, _) in self.cards.items():
            box.configure(text=captions[key])
        self.url_label.configure(text=t("app_running", url=self.url))
        self.b_open.configure(text=t("app_open"))
        self.b_browser.configure(text=t("app_browser"))
        self.b_refresh.configure(text=t("app_refresh"))
        self.b_lang.configure(text=t("app_other_lang"))
        self.b_quit.configure(text=t("app_quit"))
        self.note.configure(text=t("app_close_note"))
        self.show()

    def load(self, force: bool = False) -> None:
        if self.loading:
            return
        self.loading = True
        self.b_refresh.state(["disabled"])
        if self.data is None or force:
            self.status.configure(text=t("app_loading"))

        def work():
            try:
                self.results.put(("ok", self.httpd.get_data(force)))
            except Exception as exc:  # noqa: BLE001 - shown in the window
                self.results.put(("error", exc))

        threading.Thread(target=work, daemon=True).start()

    def poll(self) -> None:
        try:
            kind, value = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.loading = False
            self.b_refresh.state(["!disabled"])
            if kind == "ok":
                self.data = value
                self.show()
            else:
                self.status.configure(text=t("app_error", err=value))
        self.root.after(150, self.poll)

    def show(self) -> None:
        if self.data is None:
            return
        stats = summarize(self.data)
        for key, (_, value, detail) in self.cards.items():
            v, d = stats[key] if stats else ("—", " ")
            value.configure(text=v)
            detail.configure(text=d)
        if stats:
            self.status.configure(text=t("app_updated", time=datetime.now().strftime("%H:%M"),
                                         files=self.data["meta"]["files"]))
        else:
            self.status.configure(text=t("app_no_data"))

    def tick(self) -> None:
        self.load()
        self.root.after(REFRESH_MS, self.tick)

    def toggle_lang(self) -> None:
        set_lang("en" if get_lang() == "vi" else "vi")
        save_settings({**load_settings(), "lang": get_lang()})
        self.texts()
        self.load(force=True)  # the dashboard page picks up the new language too

    def quit(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="token-meter-app",
                                description="Claude Token Meter desktop app: live dashboard with a small control window.")
    p.add_argument("--version", action="version", version=f"Claude Token Meter {__version__}")
    p.add_argument("--path", action="append", metavar="DIR", help="folder with Claude Code .jsonl logs (repeatable)")
    p.add_argument("--lang", choices=sorted(STRINGS))
    p.add_argument("--no-window", action="store_true", help="only run the dashboard server, without the window")
    p.add_argument("--no-open", action="store_true", help="do not open the dashboard on start")
    p.add_argument("--self-test", action="store_true", help="check the server and the bundled files, then exit")
    opts = p.parse_args(argv)

    env = (os.environ.get("TOKEN_METER_LANG") or "").lower()
    set_lang(opts.lang or (env if env in STRINGS else "") or load_settings().get("lang") or "vi")
    args = server_args(opts.path)
    if opts.self_test:
        return self_test(args)

    httpd, url = start_server(args)
    if httpd is None:  # already running: just show it
        print(t("app_already", url=url), flush=True)
        open_dashboard(url)
        return 0

    try:
        import tkinter
    except ImportError:
        tkinter = None
    if opts.no_window or tkinter is None:
        return run_headless(httpd, url, not opts.no_open)
    try:
        app = App(tkinter, httpd, url, args.window)
    except tkinter.TclError:  # no display
        return run_headless(httpd, url, not opts.no_open)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    if not opts.no_open:
        open_dashboard(url)
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
