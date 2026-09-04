"""Display currencies. API prices are USD; convert only for the UI."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

# USD per 1 unit of currency inverted: how many units of C per 1 USD.
# Snapshot ~ 2026-08. Override with LEA_FX_CNY=7.2 etc.
RATES_PER_USD: dict[str, float] = {
    "usd": 1.0,
    "cny": 7.18,
    "eur": 0.86,
    "gbp": 0.74,
    "jpy": 147.0,
    "hkd": 7.78,
}

SYMBOLS = {
    "usd": "$",
    "cny": "¥",
    "eur": "€",
    "gbp": "£",
    "jpy": "¥",
    "hkd": "HK$",
}

PREFS_PATH = Path.home() / ".lea" / "prefs.yaml"


def _rate(currency: str) -> float:
    code = (currency or "usd").lower()
    env = os.environ.get(f"LEA_FX_{code.upper()}")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    return RATES_PER_USD.get(code, 1.0)


def normalize_currency(raw: str | None) -> str:
    code = (raw or "usd").strip().lower()
    aliases = {"rmb": "cny", "yuan": "cny", "cn": "cny", "us": "usd", "dollar": "usd", "€": "eur", "£": "gbp"}
    code = aliases.get(code, code)
    if code not in RATES_PER_USD:
        raise ValueError(f"Unsupported currency {raw!r}. Use: {', '.join(RATES_PER_USD)}")
    return code


def to_display(usd: float, currency: str) -> float:
    return usd * _rate(normalize_currency(currency))


def to_usd(amount: float, currency: str) -> float:
    rate = _rate(normalize_currency(currency))
    if rate <= 0:
        return amount
    return amount / rate


def fmt(usd: float, currency: str, *, digits: int | None = None) -> str:
    code = normalize_currency(currency)
    value = to_display(usd, code)
    if digits is None:
        digits = 0 if code == "jpy" else 3 if value < 1 else 2
    return f"{SYMBOLS[code]}{value:,.{digits}f} {code.upper()}"


def parse_money(raw: str, default_currency: str = "usd") -> tuple[float, str] | None:
    text = (raw or "").strip().lower()
    if not text or text in {"skip", "none", "no", "n", "无", "跳过", "-"}:
        return None
    text = text.replace(",", "").replace("￥", "¥")
    cur = default_currency
    if text.startswith("$"):
        cur, text = "usd", text[1:]
    elif text.startswith("¥") or text.startswith("￥"):
        cur, text = "cny", text[1:]
    elif text.startswith("€"):
        cur, text = "eur", text[1:]
    elif text.startswith("£"):
        cur, text = "gbp", text[1:]
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-z]{2,4})?$", text)
    if not m:
        return None
    amount = float(m.group(1))
    if m.group(2):
        cur = normalize_currency(m.group(2))
    else:
        cur = normalize_currency(cur)
    return amount, cur


def load_prefs() -> dict:
    if not PREFS_PATH.is_file():
        return {"currency": "cny"}
    data = yaml.safe_load(PREFS_PATH.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"currency": "cny"}


def save_prefs(prefs: dict) -> None:
    PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREFS_PATH.write_text(yaml.safe_dump(prefs, allow_unicode=True, sort_keys=False), encoding="utf-8")
