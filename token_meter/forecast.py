"""Estimate future token use from the recent rate of use.

Three estimates are combined:
  * rate  - average per day over the last ``window`` days (default 7)
  * long  - average per day over the last 30 days
  * trend - least-squares line through the daily totals of the last 30 full days
The headline number uses ``rate``; ``low``/``high`` span all three so you can
see how sure the estimate is.
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from .analysis import blocks, by_model, totals

RATE_FIELDS = ("total", "input", "output", "cache_write", "cache_read", "cost", "requests")


def _window_rate(records, now: datetime, days: float, history_days: float) -> dict:
    start = now - timedelta(days=days)
    sel = [r for r in records if start <= r.ts <= now]
    eff = max(min(days, history_days), 1 / 24)  # young history: divide by what exists
    t = totals(sel)
    per_day = {k: t[k] / eff for k in RATE_FIELDS}
    shares = {m["model"]: m["share"] for m in by_model(sel)}
    return {"days": days, "effective_days": eff, "per_day": per_day, "model_share": shares}


def daily_series(records, first_day, last_day) -> List[Tuple[str, int]]:
    """Total tokens for every local day in [first_day, last_day], zero-filled."""
    sums = {}
    for r in records:
        d = r.ts.date()
        if first_day <= d <= last_day:
            sums[d] = sums.get(d, 0) + r.total
    out, d = [], first_day
    while d <= last_day:
        out.append((d.isoformat(), sums.get(d, 0)))
        d += timedelta(days=1)
    return out


def linear_fit(ys: List[float]) -> Tuple[float, float]:
    """Return (intercept, slope) of y = a + b*x for x = 0..n-1."""
    n = len(ys)
    if n == 0:
        return 0.0, 0.0
    if n == 1:
        return float(ys[0]), 0.0
    mx = (n - 1) / 2
    my = sum(ys) / n
    var = sum((x - mx) ** 2 for x in range(n))
    cov = sum((x - mx) * (y - my) for x, y in enumerate(ys))
    slope = cov / var if var else 0.0
    return my - slope * mx, slope


def block_projection(block: dict, now: datetime) -> dict:
    elapsed = max((now - block["first"]).total_seconds() / 60, 1.0)
    remaining = max((block["end"] - now).total_seconds() / 60, 0.0)
    per_min = block["total"] / elapsed
    cost_per_min = block["cost"] / elapsed
    return {
        "elapsed_min": elapsed,
        "remaining_min": remaining,
        "tokens_per_min": per_min,
        "cost_per_hour": cost_per_min * 60,
        "projected_total": block["total"] + per_min * remaining,
        "projected_cost": block["cost"] + cost_per_min * remaining,
    }


def forecast(records, now: Optional[datetime] = None, window: int = 7) -> Optional[dict]:
    if not records:
        return None
    now = now or datetime.now().astimezone()
    history_days = max((now - records[0].ts).total_seconds() / 86400, 1 / 24)

    rate = _window_rate(records, now, window, history_days)
    long = _window_rate(records, now, 30, history_days)

    # trend over the last <=30 complete days (today is still in progress)
    today = now.date()
    last_full = today - timedelta(days=1)
    first_full = max(records[0].ts.date(), last_full - timedelta(days=29))
    series = daily_series(records, first_full, last_full) if first_full <= last_full else []
    a, b = linear_fit([v for _, v in series])
    n = len(series)

    def trend_sum(days: int) -> float:
        if not series:
            return rate["per_day"]["total"] * days
        return sum(max(a + b * (n + k), 0.0) for k in range(days))

    r7 = rate["per_day"]["total"]
    r30 = long["per_day"]["total"]
    horizons = {}
    for name, days in (("24h", 1), ("7d", 7), ("30d", 30)):
        base, alt, tr = r7 * days, r30 * days, trend_sum(days)
        horizons[name] = {
            "days": days,
            "tokens": base,
            "low": min(base, alt, tr),
            "high": max(base, alt, tr),
            "trend": tr,
            "tokens_30d_rate": alt,
            "cost": rate["per_day"]["cost"] * days,
            "cost_30d_rate": long["per_day"]["cost"] * days,
            "requests": rate["per_day"]["requests"] * days,
            "by_model": {m: base * s for m, s in rate["model_share"].items()},
        }

    # rest of the calendar month at the current rate
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    month_end = month_start + timedelta(days=days_in_month)
    mtd = totals([r for r in records if r.ts >= month_start])
    left_days = (month_end - now).total_seconds() / 86400
    end_of_month = {
        "month": now.strftime("%Y-%m"),
        "to_date": mtd["total"],
        "to_date_cost": mtd["cost"],
        "days_left": left_days,
        "tokens": mtd["total"] + r7 * left_days,
        "cost": mtd["cost"] + rate["per_day"]["cost"] * left_days,
    }

    next_days = [{"date": (today + timedelta(days=k)).isoformat(),
                  "tokens": r7,
                  "trend": max(a + b * (n + k), 0.0) if series else r7}
                 for k in range(1, 8)]

    last_hour = totals([r for r in records if r.ts >= now - timedelta(hours=1)])
    last_day = totals([r for r in records if r.ts >= now - timedelta(days=1)])

    all_blocks = blocks(records, now)
    active = next((bl for bl in reversed(all_blocks) if bl["active"]), None)
    finished = [bl["total"] for bl in all_blocks if not bl["active"]]
    current_block = None
    if active:
        current_block = {**active, **block_projection(active, now),
                         "max_past_block": max(finished) if finished else None}

    return {
        "now": now,
        "window": window,
        "history_days": history_days,
        "rate": rate,
        "rate_30d": long,
        "trend": {"intercept": a, "slope_per_day": b, "days": n},
        "horizons": horizons,
        "end_of_month": end_of_month,
        "next_days": next_days,
        "last_hour": last_hour,
        "last_24h": last_day,
        "current_block": current_block,
    }
