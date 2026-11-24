"""API-equivalent cost estimate.

Prices are USD per 1 million tokens from Anthropic's public price list
(snapshot 2026-11).  If you use Claude through a Pro/Max/Team subscription you
do not pay per token: the cost shown is what the same traffic would cost on the
API.  Override or extend the table with ``--pricing my_prices.json`` (same
shape as DEFAULT_PRICES).

Per model: ``input`` and ``output`` are required.  Optional keys:
``cache_read`` (default 0.1 x input), ``cache_write_5m`` (default 1.25 x input),
``cache_write_1h`` (default 2 x input), ``fast_multiplier`` (default 2, applied
to requests sent in fast mode) and ``long`` = {"above": N, "input": x,
"output": y} for models that charge more when the prompt exceeds N tokens.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Dict, Iterable, Optional

DEFAULT_PRICES: Dict[str, dict] = {
    # current generation
    "claude-fable-5-2": {"input": 8, "output": 40, "cache_read": 0.20},
    "claude-mythos-5-2": {"input": 8, "output": 40, "cache_read": 0.20},
    "claude-fable-5-1": {"input": 10, "output": 50, "cache_read": 0.25},
    "claude-mythos-5-1": {"input": 10, "output": 50, "cache_read": 0.25},
    "claude-fable-5": {"input": 10, "output": 50, "cache_read": 1.0},
    "claude-mythos-5": {"input": 10, "output": 50, "cache_read": 1.0},
    "claude-opus-5-5": {"input": 4, "output": 20, "cache_read": 0.20},
    "claude-opus-5": {"input": 5, "output": 25},
    "claude-sonnet-5-5": {"input": 2, "output": 10, "cache_read": 0.10},
    "claude-sonnet-5": {"input": 2, "output": 10},
    "claude-haiku-5-5": {"input": 0.10, "output": 0.50,
                         "long": {"above": 100_000, "input": 0.50, "output": 2.50}},
    # previous generations
    "claude-opus-4-8": {"input": 5, "output": 25},
    "claude-opus-4-7": {"input": 5, "output": 25},
    "claude-opus-4-6": {"input": 5, "output": 25},
    "claude-opus-4-5": {"input": 5, "output": 25},
    "claude-opus-4-1": {"input": 15, "output": 75},
    "claude-opus-4": {"input": 15, "output": 75},
    "claude-sonnet-4-6": {"input": 3, "output": 15},
    "claude-sonnet-4-5": {"input": 3, "output": 15},
    "claude-sonnet-4": {"input": 3, "output": 15},
    "claude-3-7-sonnet": {"input": 3, "output": 15},
    "claude-3-5-sonnet": {"input": 3, "output": 15},
    "claude-haiku-4-5": {"input": 1, "output": 5},
    "claude-3-5-haiku": {"input": 0.80, "output": 4},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


def normalize_model(model: str) -> str:
    """'us.anthropic.claude-opus-4-1-20250805-v1:0[1m]' -> 'claude-opus-4-1-20250805-v1:0'."""
    m = model.lower().strip()
    m = re.sub(r"\[.*?\]$", "", m)
    i = m.find("claude-")
    return m[i:] if i >= 0 else m


class Pricer:
    def __init__(self, prices: Optional[Dict[str, dict]] = None):
        self.prices = dict(DEFAULT_PRICES)
        if prices:
            self.prices.update(prices)
        # longest key first so 'claude-opus-4-1' wins over 'claude-opus-4'
        self._keys = sorted(self.prices, key=len, reverse=True)
        self.lookup = lru_cache(maxsize=None)(self._lookup)

    def _lookup(self, model: str) -> Optional[dict]:
        m = normalize_model(model)
        for key in self._keys:
            if m == key or m.startswith(key + "-") or m.startswith(key + "@"):
                return self.prices[key]
        return None

    def cost(self, rec) -> Optional[float]:
        p = self.lookup(rec.model)
        if p is None:
            return None
        inp, out = float(p["input"]), float(p["output"])
        cache_read = p.get("cache_read")
        long = p.get("long")
        prompt = rec.input + rec.cache_write + rec.cache_read
        if long and prompt > long["above"]:
            inp, out, cache_read = float(long["input"]), float(long["output"]), None
        if cache_read is None:
            cache_read = inp * 0.1
        w5 = p.get("cache_write_5m", inp * 1.25)
        w1 = p.get("cache_write_1h", inp * 2)
        usd = (rec.input * inp + rec.output * out + rec.cache_5m * w5
               + rec.cache_1h * w1 + rec.cache_read * cache_read) / 1_000_000
        if rec.speed == "fast":
            usd *= p.get("fast_multiplier", 2)
        return usd


def load_prices(path: Optional[str]) -> Optional[Dict[str, dict]]:
    if not path:
        return None
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("pricing file must be a JSON object: {model: {input, output, ...}}")
    return data


def apply_pricing(records: Iterable, pricer: Pricer) -> set:
    """Set rec.cost for every record; return the set of models with no price."""
    unknown = set()
    for r in records:
        c = pricer.cost(r)
        if c is None:
            unknown.add(r.model)
            r.cost = 0.0
        else:
            r.cost = c
    return unknown
