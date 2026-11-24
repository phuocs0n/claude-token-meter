"""Find Claude Code transcript files (*.jsonl) and turn them into usage records.

Claude Code (CLI, desktop app, IDE extensions, Agent SDK) writes one JSONL file
per session under ``<config dir>/projects/<project>/<session>.jsonl``.  Every
assistant reply carries ``message.usage`` with the token counts the API billed.
A single reply is often written several times while it streams, so records are
de-duplicated on ``(message.id, requestId)`` and the most complete copy is kept.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Iterator, List, Optional


@dataclass
class Record:
    ts: datetime  # timezone-aware, converted to local time
    model: str
    input: int
    output: int
    cache_5m: int
    cache_1h: int
    cache_read: int
    session: str
    project: str
    speed: str = "standard"
    sidechain: bool = False
    cost: float = 0.0  # filled in by pricing.apply_pricing

    @property
    def cache_write(self) -> int:
        return self.cache_5m + self.cache_1h

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_5m + self.cache_1h + self.cache_read


@dataclass
class LoadResult:
    records: List[Record]
    roots: List[str]
    files: int = 0
    lines_with_usage: int = 0
    duplicates: int = 0
    bad_lines: int = 0
    errors: List[str] = field(default_factory=list)


def default_roots() -> List[str]:
    """Claude Code data folders that exist on this machine."""
    candidates = []
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        candidates += [os.path.join(p.strip(), "projects") for p in env.split(",") if p.strip()]
    home = os.path.expanduser("~")
    candidates += [
        os.path.join(home, ".claude", "projects"),
        os.path.join(home, ".config", "claude", "projects"),
    ]
    out, seen = [], set()
    for c in candidates:
        key = os.path.normcase(os.path.abspath(c))
        if key not in seen and os.path.isdir(c):
            seen.add(key)
            out.append(os.path.abspath(c))
    return out


def _long_path(p: str) -> str:
    """Windows refuses paths over 260 chars unless they use the \\\\?\\ prefix."""
    if os.name != "nt" or p.startswith("\\\\?\\"):
        return p
    p = os.path.abspath(p)
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def find_files(roots: Iterable[str]) -> Iterator[str]:
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, _dirs, files in os.walk(root):
            for name in files:
                if name.endswith(".jsonl"):
                    yield os.path.join(dirpath, name)


def parse_ts(value) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def _int(v) -> int:
    try:
        return max(int(v or 0), 0)
    except (TypeError, ValueError):
        return 0


def parse_entry(d: dict, fallback_session: str = "", fallback_project: str = "") -> Optional[Record]:
    """Build a Record from one decoded JSONL line, or None if it has no usage."""
    msg = d.get("message")
    if not isinstance(msg, dict):
        return None
    usage = msg.get("usage")
    if not isinstance(usage, dict):
        return None
    model = msg.get("model") or "unknown"
    if model == "<synthetic>":  # local placeholder messages, never sent to the API
        return None
    ts = parse_ts(d.get("timestamp"))
    if ts is None:
        return None

    write_total = _int(usage.get("cache_creation_input_tokens"))
    split = usage.get("cache_creation") if isinstance(usage.get("cache_creation"), dict) else {}
    c1h = min(_int(split.get("ephemeral_1h_input_tokens")), write_total)
    c5m = write_total - c1h  # anything not marked 1h is billed as a 5-minute write

    return Record(
        ts=ts,
        model=model,
        input=_int(usage.get("input_tokens")),
        output=_int(usage.get("output_tokens")),
        cache_5m=c5m,
        cache_1h=c1h,
        cache_read=_int(usage.get("cache_read_input_tokens")),
        session=d.get("sessionId") or fallback_session,
        project=d.get("cwd") or fallback_project,
        speed=usage.get("speed") or "standard",
        sidechain=bool(d.get("isSidechain")),
    )


def load(roots: Optional[List[str]] = None) -> LoadResult:
    roots = roots or default_roots()
    result = LoadResult(records=[], roots=list(roots))
    best = {}  # (message id, request id) -> Record
    loose: List[Record] = []

    for path in find_files(roots):
        result.files += 1
        session = os.path.splitext(os.path.basename(path))[0]
        project = os.path.basename(os.path.dirname(path))
        try:
            fh = open(_long_path(path), encoding="utf-8", errors="replace")
        except OSError as exc:
            result.errors.append(f"{path}: {exc}")
            continue
        with fh:
            for line in fh:
                if '"usage"' not in line:  # cheap pre-filter, skips most lines
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    result.bad_lines += 1
                    continue
                if not isinstance(d, dict):
                    continue
                rec = parse_entry(d, session, project)
                if rec is None:
                    continue
                result.lines_with_usage += 1
                msg_id = d["message"].get("id")
                if not msg_id:
                    loose.append(rec)
                    continue
                key = (msg_id, d.get("requestId"))
                old = best.get(key)
                if old is None:
                    best[key] = rec
                else:
                    result.duplicates += 1
                    if rec.total > old.total:  # streaming copies grow; keep the final one
                        rec.ts = min(rec.ts, old.ts)
                        best[key] = rec

    result.records = sorted(list(best.values()) + loose, key=lambda r: r.ts)
    return result


def filter_records(records, since=None, until=None, models=None, project=None):
    """since/until are aware datetimes; models is a list of substrings."""
    out = []
    models = [m.lower() for m in models] if models else None
    project = project.lower() if project else None
    for r in records:
        if since and r.ts < since:
            continue
        if until and r.ts >= until:
            continue
        if models and not any(m in r.model.lower() for m in models):
            continue
        if project and project not in r.project.lower():
            continue
        out.append(r)
    return out
