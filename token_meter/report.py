"""Plain-text tables for the terminal."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from . import analysis
from .i18n import t

FULL_NUMBERS = False


def num(n: float) -> str:
    if FULL_NUMBERS:
        return f"{int(round(n)):,}"
    a = abs(n)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= div:
            return f"{n / div:.2f}{suffix}"
    return f"{n:.0f}"


def usd(x: float) -> str:
    return f"${x:,.2f}"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def short_model(m: str) -> str:
    return m[7:] if m.startswith("claude-") else m


def short_path(p: str, width: int = 42) -> str:
    return p if len(p) <= width else "…" + p[-(width - 1):]


def when(d: datetime) -> str:
    return d.strftime("%Y-%m-%d %H:%M")


def duration(minutes: float) -> str:
    h, m = divmod(int(round(minutes)), 60)
    return f"{h}h{m:02d}m"


def bar(frac: float, width: int = 14) -> str:
    cells = max(frac, 0.0) * width
    full = int(cells)
    return "█" * full + ("▌" if cells - full >= 0.5 else "")


def table(headers: List[str], rows: List[list], right=()) -> str:
    right = set(right)
    widths = [max([len(str(h))] + [len(str(r[i])) for r in rows]) for i, h in enumerate(headers)]

    def fmt(row):
        cells = [str(c).rjust(w) if i in right else str(c).ljust(w)
                 for i, (c, w) in enumerate(zip(row, widths))]
        return " " + "  ".join(cells).rstrip()

    return "\n".join([fmt(headers), " " + "  ".join("─" * w for w in widths)] + [fmt(r) for r in rows])


def header(res, records) -> str:
    a, b = records[0].ts, records[-1].ts
    days = (b.date() - a.date()).days + 1
    return "\n".join([
        t("header", a=a.strftime("%Y-%m-%d"), b=b.strftime("%Y-%m-%d"), days=days),
        t("scanned", files=res.files, req=f"{len(records):,}", dups=f"{res.duplicates:,}"),
    ])


def token_cols(b: dict) -> list:
    return [num(b["input"]), num(b["output"]), num(b["cache_write"]), num(b["cache_read"]),
            num(b["total"]), usd(b["cost"])]


TOKEN_HEADERS = ["input", "output", "cache_write", "cache_read", "total", "cost"]


def models_table(records) -> str:
    rows = []
    for m in analysis.by_model(records):
        rows.append([short_model(m["model"]), f"{m['requests']:,}", *token_cols(m),
                     f"{pct(m['share']):>6} {bar(m['share'])}"])
    heads = [t("model"), t("requests")] + [t(h) for h in TOKEN_HEADERS] + [t("share")]
    return table(heads, rows, right=range(1, 8))


def render_summary(res, records, fc, unknown) -> str:
    tot = analysis.totals(records)
    out = [header(res, records), "", t("totals")]
    for key in ("input", "output", "cache_write", "cache_read"):
        out.append(f"  {t(key):<12}{num(tot[key]):>12}")
    out.append(f"  {t('total'):<12}{num(tot['total']):>12}   ≈ {usd(tot['cost'])}")
    out += ["", t("by_model"), models_table(records)]
    if fc:
        out += ["", render_forecast(fc, brief=True)]
    out += ["", t("cost_note")]
    if unknown:
        out.append(t("unknown_models", models=", ".join(sorted(unknown))))
    return "\n".join(out)


def render_models(records) -> str:
    rows = []
    for m in sorted(analysis.by_model(records), key=lambda g: g["first"]):
        rows.append([short_model(m["model"]), when(m["first"]), when(m["last"]), m["days_used"],
                     f"{m['requests']:,}", num(m["total"]), usd(m["cost"]), pct(m["share"])])
    heads = [t("model"), t("first"), t("last"), t("days"), t("requests"), t("total"), t("cost"), t("share")]
    out = [t("history"), table(heads, rows, right=range(3, 8)), "", t("switches")]
    for s in analysis.model_switches(records):
        if s["previous"] is None:
            out.append("  " + t("first_model", date=s["date"], model=short_model(s["model"])))
        else:
            out.append("  " + t("switch_row", date=s["date"], prev=short_model(s["previous"]),
                                model=short_model(s["model"]), share=pct(s["share"])))
    return "\n".join(out)


def render_periods(records, period: str, limit: Optional[int] = None) -> str:
    groups = analysis.by_period(records, period)
    if limit:
        groups = groups[-limit:]
    rows = []
    for g in groups:
        top = ", ".join(f"{short_model(m)} {pct(v / g['total'] if g['total'] else 0)}"
                        for m, v in list(g["models"].items())[:3])
        rows.append([g["period"], f"{g['requests']:,}", *token_cols(g), top])
    heads = [t(period), t("requests")] + [t(h) for h in TOKEN_HEADERS] + [t("models")]
    return table(heads, rows, right=range(1, 8))


def render_groups(records, attr: str, limit: int) -> str:
    rows = []
    for g in analysis.group_by(records, attr, limit):
        models = ", ".join(short_model(m) for m in list(g["models"])[:2])
        if attr == "session":
            label = [g["key"][:8], short_path(g["project"], 32)]
        else:
            label = [short_path(g["key"]), g["sessions"]]
        rows.append(label + [when(g["first"]), when(g["last"]), f"{g['requests']:,}",
                             num(g["total"]), usd(g["cost"]), models])
    first = [t("session"), t("project")] if attr == "session" else [t("project"), t("sessions")]
    heads = first + [t("start"), t("end"), t("requests"), t("total"), t("cost"), t("models")]
    right = {4, 5, 6} if attr == "session" else {1, 4, 5, 6}
    return table(heads, rows, right=right)


def render_blocks(records, limit: int, now: datetime) -> str:
    rows = []
    for b in analysis.blocks(records, now)[-limit:]:
        rows.append([b["start"].strftime("%Y-%m-%d %H:%M"), b["end"].strftime("%H:%M"),
                     t("active") if b["active"] else "", f"{b['requests']:,}", num(b["total"]),
                     usd(b["cost"]), ", ".join(short_model(m) for m in list(b["models"])[:2])])
    heads = [t("start"), t("end"), "", t("requests"), t("total"), t("cost"), t("models")]
    return t("blocks") + "\n" + table(heads, rows, right={3, 4, 5})


def render_block(cb) -> str:
    if not cb:
        return t("block") + "\n  " + t("no_block")
    lines = [t("block"),
             "  " + t("block_line", start=cb["start"].strftime("%H:%M"), end=cb["end"].strftime("%H:%M"),
                      left=duration(cb["remaining_min"]), used=num(cb["total"]), cost=usd(cb["cost"])),
             "  " + t("block_rate", rate=num(cb["tokens_per_min"]), per_min=t("per_min"),
                      proj=num(cb["projected_total"]), pcost=usd(cb["projected_cost"]))]
    if cb.get("max_past_block"):
        lines.append("  " + t("block_max", mx=num(cb["max_past_block"]),
                              pct=pct(cb["total"] / cb["max_past_block"])))
    return "\n".join(lines)


def render_forecast(fc, brief: bool = False) -> str:
    rate = fc["rate"]["per_day"]
    out = [t("forecast", w=fc["window"]),
           f"  {t('rate')}: {num(rate['total'])} token{t('per_day')} · {usd(rate['cost'])}{t('per_day')}"
           f" · {rate['requests']:.0f} {t('requests').lower()}{t('per_day')}"]
    rows = []
    for key in ("24h", "7d", "30d"):
        h = fc["horizons"][key]
        rows.append([t("next_" + key), num(h["tokens"]), usd(h["cost"]),
                     num(h["tokens_30d_rate"]), usd(h["cost_30d_rate"]), num(h["trend"])])
    heads = ["", t("by_rate", w=fc["window"]), t("cost"), t("by_rate", w=30), t("cost"), t("trend_col")]
    out.append(table(heads, rows, right=range(1, 6)))
    eom = fc["end_of_month"]
    out.append(f"  {t('eom', m=eom['month'])}: {num(eom['tokens'])} ≈ {usd(eom['cost'])}  "
               f"({t('eom_detail', done=num(eom['to_date']), left=eom['days_left'])})")
    if not brief:
        slope = fc["trend"]["slope_per_day"]
        out.append("  " + t("trend", dir=t("up") if slope >= 0 else t("down"), v=num(abs(slope))))
        out.append(f"  {t('last_hour'):<14}{num(fc['last_hour']['total']):>10}  ≈ {usd(fc['last_hour']['cost']):>10}")
        out.append(f"  {t('last_24h'):<14}{num(fc['last_24h']['total']):>10}  ≈ {usd(fc['last_24h']['cost']):>10}")
        out += ["", t("by_model_30d")]
        h30 = fc["horizons"]["30d"]
        for m, v in sorted(h30["by_model"].items(), key=lambda kv: -kv[1]):
            share = v / h30["tokens"] if h30["tokens"] else 0
            out.append(f"  {short_model(m):<16}{num(v):>10}  {pct(share):>6} {bar(share)}")
    out += ["", render_block(fc["current_block"])]
    return "\n".join(out)
