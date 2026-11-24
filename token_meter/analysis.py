"""Aggregations over usage records: totals, per model, per period, sessions, 5-hour blocks."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

TOKEN_FIELDS = ("input", "output", "cache_write", "cache_read")


def bucket() -> dict:
    return {"requests": 0, "input": 0, "output": 0, "cache_write": 0,
            "cache_read": 0, "total": 0, "cost": 0.0}


def add(b: dict, r) -> None:
    b["requests"] += 1
    b["input"] += r.input
    b["output"] += r.output
    b["cache_write"] += r.cache_write
    b["cache_read"] += r.cache_read
    b["total"] += r.total
    b["cost"] += r.cost


def totals(records) -> dict:
    b = bucket()
    for r in records:
        add(b, r)
    return b


def _sorted_models(counts: dict) -> dict:
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))


def period_key(ts: datetime, period: str) -> str:
    if period == "day":
        return ts.strftime("%Y-%m-%d")
    if period == "week":
        year, week, _ = ts.isocalendar()
        return f"{year}-W{week:02d}"
    if period == "month":
        return ts.strftime("%Y-%m")
    if period == "hour":
        return ts.strftime("%Y-%m-%d %H:00")
    raise ValueError(f"unknown period {period!r}")


def by_model(records) -> List[dict]:
    groups = {}
    for r in records:
        g = groups.get(r.model)
        if g is None:
            g = groups[r.model] = {"model": r.model, **bucket(), "first": r.ts, "last": r.ts, "_days": set()}
        add(g, r)
        if r.ts < g["first"]:
            g["first"] = r.ts
        if r.ts > g["last"]:
            g["last"] = r.ts
        g["_days"].add(r.ts.date())
    grand = sum(g["total"] for g in groups.values()) or 1
    out = []
    for g in groups.values():
        g["days_used"] = len(g.pop("_days"))
        g["share"] = g["total"] / grand
        out.append(g)
    return sorted(out, key=lambda g: g["total"], reverse=True)


def by_period(records, period: str = "day") -> List[dict]:
    """Records must be sorted by time; periods come out in chronological order."""
    groups = {}
    for r in records:
        k = period_key(r.ts, period)
        g = groups.get(k)
        if g is None:
            g = groups[k] = {"period": k, **bucket(), "models": defaultdict(int)}
        add(g, r)
        g["models"][r.model] += r.total
    out = list(groups.values())
    for g in out:
        g["models"] = _sorted_models(g["models"])
    return out


def model_switches(records) -> List[dict]:
    """Days on which the main model (the one with the most tokens that day) changed."""
    out, prev = [], None
    for day in by_period(records, "day"):
        if not day["models"]:
            continue
        top = next(iter(day["models"]))
        if top != prev:
            share = day["models"][top] / day["total"] if day["total"] else 0.0
            out.append({"date": day["period"], "model": top, "previous": prev, "share": share})
            prev = top
    return out


def group_by(records, attr: str, limit: Optional[int] = None) -> List[dict]:
    """Group by 'session' or 'project'."""
    groups = {}
    for r in records:
        k = getattr(r, attr) or "?"
        g = groups.get(k)
        if g is None:
            g = groups[k] = {"key": k, **bucket(), "first": r.ts, "last": r.ts,
                             "models": defaultdict(int), "project": r.project, "_sessions": set()}
        add(g, r)
        g["first"] = min(g["first"], r.ts)
        g["last"] = max(g["last"], r.ts)
        g["models"][r.model] += r.total
        g["_sessions"].add(r.session)
    out = sorted(groups.values(), key=lambda g: g["total"], reverse=True)
    for g in out:
        g["models"] = _sorted_models(g["models"])
        g["sessions"] = len(g.pop("_sessions"))
    return out[:limit] if limit else out


def blocks(records, now: Optional[datetime] = None, hours: int = 5) -> List[dict]:
    """Split usage into rolling windows the way Claude plans meter it.

    A window opens at the top of the hour of the first request and lasts
    ``hours``; the first request after it closes opens the next one.
    """
    now = now or datetime.now().astimezone()
    span = timedelta(hours=hours)
    out, cur = [], None
    for r in records:
        if cur is None or r.ts >= cur["end"]:
            start = r.ts.replace(minute=0, second=0, microsecond=0)
            cur = {"start": start, "end": start + span, "first": r.ts, "last": r.ts,
                   **bucket(), "models": defaultdict(int)}
            out.append(cur)
        add(cur, r)
        cur["last"] = r.ts
        cur["models"][r.model] += r.total
    for b in out:
        b["models"] = _sorted_models(b["models"])
        b["active"] = b["start"] <= now < b["end"]
    return out


def hour_of_day(records) -> List[int]:
    """Total tokens per local hour of day (0-23)."""
    hours = [0] * 24
    for r in records:
        hours[r.ts.hour] += r.total
    return hours
