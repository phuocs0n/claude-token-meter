"""Command line entry point: ``token-meter [command] [options]``."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from . import __version__, analysis, loader, report
from .forecast import forecast
from .i18n import default_lang, set_lang, t
from .pricing import Pricer, apply_pricing, load_prices

COMMANDS = {
    "summary": "Tổng quan: token theo loại, theo model, dự báo nhanh (mặc định) / overview (default)",
    "models": "Lịch sử model: lần đầu/gần nhất, các lần đổi model / model history",
    "daily": "Token theo ngày / tokens per day",
    "weekly": "Token theo tuần / tokens per week",
    "monthly": "Token theo tháng / tokens per month",
    "sessions": "Các phiên dùng nhiều token nhất / top sessions",
    "projects": "Token theo dự án (thư mục) / tokens per project",
    "blocks": "Các cửa sổ 5 giờ / 5-hour usage windows",
    "forecast": "Dự báo token sẽ dùng theo tốc độ hiện tại / forecast at the current rate",
    "dashboard": "Tạo dashboard HTML và mở trong trình duyệt / write an HTML dashboard",
    "serve": "Chạy dashboard trực tiếp, tự cập nhật / serve a live dashboard",
}


def _date(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").astimezone()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    g = common.add_argument_group("options")
    g.add_argument("--path", action="append", metavar="DIR",
                   help="thư mục/file .jsonl cần đọc (lặp lại được). Mặc định ~/.claude/projects")
    g.add_argument("--since", type=_date, metavar="YYYY-MM-DD", help="chỉ lấy từ ngày này")
    g.add_argument("--until", type=_date, metavar="YYYY-MM-DD", help="chỉ lấy đến hết ngày này")
    g.add_argument("--days", type=int, metavar="N", help="chỉ lấy N ngày gần nhất")
    g.add_argument("--model", action="append", metavar="TEXT", help="lọc model chứa chuỗi này, vd. opus")
    g.add_argument("--project", metavar="TEXT", help="lọc dự án có đường dẫn chứa chuỗi này")
    g.add_argument("--window", type=int, default=7, metavar="N",
                   help="số ngày gần nhất dùng để tính tốc độ dự báo (mặc định 7)")
    g.add_argument("--limit", type=int, default=15, metavar="N", help="số dòng tối đa cho sessions/projects/blocks")
    g.add_argument("--pricing", metavar="FILE", help="file JSON giá token để ghi đè bảng giá mặc định")
    g.add_argument("--json", action="store_true", help="in kết quả dạng JSON")
    g.add_argument("--full", action="store_true", help="in số đầy đủ thay vì 1.2M")
    g.add_argument("--lang", choices=["vi", "en"], help="ngôn ngữ (hoặc biến môi trường TOKEN_METER_LANG)")

    p = argparse.ArgumentParser(
        prog="token-meter",
        description="Xem model Claude đã dùng, lượng token và dự báo token sẽ dùng, "
                    "từ log cục bộ của Claude Code / Claude desktop.")
    p.add_argument("--version", action="version", version=f"token-meter {__version__}")
    sub = p.add_subparsers(dest="command", metavar="COMMAND")
    for name, text in COMMANDS.items():
        sp = sub.add_parser(name, parents=[common], help=text, description=text)
        if name == "dashboard":
            sp.add_argument("--out", default="token-meter-dashboard.html", help="file HTML đầu ra")
            sp.add_argument("--no-open", action="store_true", help="không tự mở trình duyệt")
        if name == "serve":
            sp.add_argument("--host", default="127.0.0.1")
            sp.add_argument("--port", type=int, default=8765)
            sp.add_argument("--no-open", action="store_true", help="không tự mở trình duyệt")
    return p


def collect(args):
    """Load, price and filter records according to the CLI options."""
    res = loader.load(args.path or None)
    pricer = Pricer(load_prices(args.pricing))
    unknown = apply_pricing(res.records, pricer)
    since, until = args.since, args.until
    if until:
        until = until + timedelta(days=1)
    if args.days:
        start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        since = max(filter(None, [since, start - timedelta(days=args.days - 1)]))
    records = loader.filter_records(res.records, since, until, args.model, args.project)
    return res, records, unknown


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, set):
        return sorted(o)
    raise TypeError(type(o).__name__)


def _utf8_stdout() -> None:
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower().replace("-", "")
        if enc != "utf8" and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or (argv[0].startswith("-") and argv[0] not in ("-h", "--help", "--version")):
        argv.insert(0, "summary")
    args = build_parser().parse_args(argv)
    _utf8_stdout()
    set_lang(args.lang or default_lang())
    report.FULL_NUMBERS = args.full

    if args.command == "serve":
        from . import dashboard
        return dashboard.serve(args, collect)

    res, records, unknown = collect(args)
    if not records:
        print(t("no_data", roots=", ".join(res.roots) or "-"), file=sys.stderr)
        return 1
    now = datetime.now().astimezone()
    cmd = args.command

    if cmd == "dashboard":
        from . import dashboard
        path = dashboard.write(args.out, dashboard.payload(res, records, unknown, args.window, now))
        print(t("dashboard_written", path=path))
        if not args.no_open:
            import webbrowser
            webbrowser.open(path.as_uri())
        return 0

    if cmd == "summary":
        fc = forecast(records, now, args.window)
        data = {"totals": analysis.totals(records), "models": analysis.by_model(records),
                "forecast": fc, "unknown_models": unknown}
        text = lambda: report.render_summary(res, records, fc, unknown)
    elif cmd == "models":
        data = {"models": analysis.by_model(records), "switches": analysis.model_switches(records)}
        text = lambda: report.render_models(records)
    elif cmd in ("daily", "weekly", "monthly"):
        period = {"daily": "day", "weekly": "week", "monthly": "month"}[cmd]
        data = analysis.by_period(records, period)
        text = lambda: report.render_periods(records, period)
    elif cmd in ("sessions", "projects"):
        attr = cmd[:-1]
        data = analysis.group_by(records, attr, args.limit)
        text = lambda: report.render_groups(records, attr, args.limit)
    elif cmd == "blocks":
        data = analysis.blocks(records, now)[-args.limit:]
        text = lambda: report.render_blocks(records, args.limit, now)
    elif cmd == "forecast":
        data = forecast(records, now, args.window)
        text = lambda: report.render_forecast(data)
    else:  # pragma: no cover - argparse restricts the choices
        raise SystemExit(f"unknown command {cmd}")

    if args.json:
        print(json.dumps(data, default=_json_default, ensure_ascii=False, indent=2))
    else:
        if cmd not in ("summary",):
            print(report.header(res, records) + "\n")
        print(text())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
