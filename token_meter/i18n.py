"""Terminal labels in Vietnamese (default) and English."""
from __future__ import annotations

import os

STRINGS = {
    "vi": {
        "no_data": "Không tìm thấy dữ liệu sử dụng. Đã tìm trong: {roots}\nDùng --path để chỉ thư mục chứa file .jsonl của Claude Code.",
        "header": "Claude Token Meter · dữ liệu {a} → {b} ({days} ngày)",
        "scanned": "{files} file · {req} request · {dups} bản ghi trùng đã gộp",
        "totals": "TỔNG TOKEN",
        "by_model": "THEO MODEL",
        "input": "Input", "output": "Output", "cache_write": "Ghi cache", "cache_read": "Đọc cache",
        "total": "Tổng", "cost": "Chi phí*", "requests": "Request", "model": "Model",
        "first": "Dùng lần đầu", "last": "Dùng gần nhất", "days": "Số ngày", "share": "Tỷ trọng",
        "cost_note": "* Chi phí ước tính theo giá API công khai (USD). Gói Pro/Max không tính theo token.",
        "unknown_models": "Model chưa có giá (tính $0): {models}",
        "history": "LỊCH SỬ MODEL",
        "switches": "Các lần đổi model chính (model dùng nhiều token nhất trong ngày)",
        "switch_row": "{date}  {prev} → {model}  ({share} token trong ngày)",
        "first_model": "{date}  bắt đầu với {model}",
        "day": "Ngày", "week": "Tuần", "month": "Tháng", "models": "Model",
        "session": "Phiên", "project": "Dự án", "start": "Bắt đầu", "end": "Kết thúc", "sessions": "Số phiên",
        "forecast": "DỰ BÁO (theo tốc độ {w} ngày gần nhất)",
        "rate": "Tốc độ", "per_day": "/ngày", "per_hour": "/giờ", "per_min": "/phút",
        "next_24h": "24 giờ tới", "next_7d": "7 ngày tới", "next_30d": "30 ngày tới",
        "by_rate": "Theo {w} ngày", "trend_col": "Theo xu hướng",
        "eom": "Hết tháng {m}", "eom_detail": "đã dùng {done}, còn {left:.1f} ngày",
        "trend": "Xu hướng 30 ngày: lượng dùng mỗi ngày {dir} khoảng {v} token so với ngày trước",
        "up": "tăng", "down": "giảm",
        "last_hour": "1 giờ qua", "last_24h": "24 giờ qua",
        "by_model_30d": "Phân bổ 30 ngày tới theo model",
        "block": "PHIÊN 5 GIỜ HIỆN TẠI",
        "no_block": "Không có phiên 5 giờ nào đang mở.",
        "block_line": "{start} → {end} · còn {left} · đã dùng {used} ({cost})",
        "block_rate": "Tốc độ {rate}{per_min} → dự kiến {proj} ({pcost}) khi hết phiên",
        "block_max": "Phiên lớn nhất trước đây: {mx} → hiện tại bằng {pct} mức đó",
        "blocks": "CÁC PHIÊN 5 GIỜ GẦN ĐÂY",
        "active": "đang mở",
        "dashboard_written": "Đã tạo dashboard: {path}",
        "serving": "Dashboard đang chạy tại {url}  (Ctrl+C để dừng)",
        "port_busy": "Không mở được cổng {port}: cổng đang bận hoặc bị chặn ({err}).\nThử cổng khác, ví dụ: token-meter serve --port {alt}",
    },
    "en": {
        "no_data": "No usage data found. Searched: {roots}\nUse --path to point at the folder with Claude Code .jsonl files.",
        "header": "Claude Token Meter · data {a} → {b} ({days} days)",
        "scanned": "{files} files · {req} requests · {dups} duplicate lines merged",
        "totals": "TOTAL TOKENS",
        "by_model": "BY MODEL",
        "input": "Input", "output": "Output", "cache_write": "Cache write", "cache_read": "Cache read",
        "total": "Total", "cost": "Cost*", "requests": "Requests", "model": "Model",
        "first": "First used", "last": "Last used", "days": "Days", "share": "Share",
        "cost_note": "* Estimated at public API prices (USD). Pro/Max plans are not billed per token.",
        "unknown_models": "Models without a price (counted as $0): {models}",
        "history": "MODEL HISTORY",
        "switches": "Changes of main model (the model with most tokens that day)",
        "switch_row": "{date}  {prev} → {model}  ({share} of that day's tokens)",
        "first_model": "{date}  started with {model}",
        "day": "Day", "week": "Week", "month": "Month", "models": "Models",
        "session": "Session", "project": "Project", "start": "Start", "end": "End", "sessions": "Sessions",
        "forecast": "FORECAST (at the rate of the last {w} days)",
        "rate": "Rate", "per_day": "/day", "per_hour": "/hour", "per_min": "/min",
        "next_24h": "Next 24 hours", "next_7d": "Next 7 days", "next_30d": "Next 30 days",
        "by_rate": "At {w}-day rate", "trend_col": "By trend",
        "eom": "End of {m}", "eom_detail": "{done} used so far, {left:.1f} days left",
        "trend": "30-day trend: daily use {dir} by about {v} tokens per day",
        "up": "rises", "down": "falls",
        "last_hour": "Last hour", "last_24h": "Last 24 hours",
        "by_model_30d": "Next 30 days by model",
        "block": "CURRENT 5-HOUR WINDOW",
        "no_block": "No 5-hour window is open right now.",
        "block_line": "{start} → {end} · {left} left · {used} used ({cost})",
        "block_rate": "Rate {rate}{per_min} → about {proj} ({pcost}) by the end of the window",
        "block_max": "Largest past window: {mx} → current is {pct} of that",
        "blocks": "RECENT 5-HOUR WINDOWS",
        "active": "open",
        "dashboard_written": "Dashboard written to {path}",
        "serving": "Dashboard running at {url}  (Ctrl+C to stop)",
        "port_busy": "Could not open port {port}: it is in use or blocked ({err}).\nTry another port, for example: token-meter serve --port {alt}",
    },
}

_lang = "vi"


def default_lang() -> str:
    env = (os.environ.get("TOKEN_METER_LANG") or "").lower()
    return env if env in STRINGS else "vi"


def set_lang(lang: str) -> None:
    global _lang
    _lang = lang if lang in STRINGS else "vi"


def get_lang() -> str:
    return _lang


def t(key: str, **kw) -> str:
    s = STRINGS[_lang].get(key) or STRINGS["en"].get(key) or key
    return s.format(**kw) if kw else s
