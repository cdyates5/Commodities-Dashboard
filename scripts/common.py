"""Shared helpers for all refresh scripts.

Every dashboard in dashboards/ is a self-contained HTML file with a single
JSON payload assigned to a JS variable (PAYLOAD, DATA or P). The refresh
pattern is always: extract payload -> recompute series from live sources ->
inject payload back. Structure is preserved, so the dashboard JS never changes.
"""
import os, re, json, time, datetime as dt
import requests
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASH = os.path.join(ROOT, "dashboards")
DATA = os.path.join(ROOT, "data")
SITE = os.path.join(ROOT, "site")
HDR = {"User-Agent": "Mozilla/5.0 (compatible; AcheronDashboards/1.0)"}

FRED_KEY = os.environ.get("FRED_API_KEY", "").strip()


# ---------------------------------------------------------------- payload I/O
def extract_payload(path):
    """Return (var_name, payload_dict, start_idx, end_idx) for a dashboard."""
    html = open(path, encoding="utf-8").read()
    m = re.search(r"\b(?:const\s+|var\s+|let\s+)?(PAYLOAD|DATA|P)\s*=\s*\{", html)
    if not m:
        raise RuntimeError(f"no payload found in {path}")
    start = html.index("{", m.start())
    depth = 0; instr = False; esc = False
    for j in range(start, len(html)):
        ch = html[j]
        if instr:
            if esc: esc = False
            elif ch == "\\": esc = True
            elif ch == '"': instr = False
        else:
            if ch == '"': instr = True
            elif ch == "{": depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return m.group(1), json.loads(html[start:j + 1]), start, j + 1
    raise RuntimeError(f"unterminated payload in {path}")


def inject_payload(path, payload, start, end):
    html = open(path, encoding="utf-8").read()
    out = html[:start] + json.dumps(payload, separators=(",", ":")) + html[end:]
    open(path, "w", encoding="utf-8").write(out)
    return len(out)


def today_str():
    return dt.date.today().strftime("%d %b %Y")


# ------------------------------------------------------------------ data feeds
def fred(series_id, retries=3):
    """Monthly/quarterly FRED series -> pd.Series indexed by PeriodIndex('M')."""
    if not FRED_KEY:
        raise RuntimeError("FRED_API_KEY not set (add it as a GitHub secret)")
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={FRED_KEY}&file_type=json")
    for a in range(retries):
        try:
            r = requests.get(url, timeout=45, headers=HDR)
            if r.status_code == 200:
                obs = [o for o in r.json()["observations"] if o["value"] not in (".", "")]
                if obs:
                    return pd.Series(
                        {pd.Period(o["date"][:7], "M"): float(o["value"]) for o in obs}
                    ).sort_index()
        except Exception:
            pass
        time.sleep(1 + a)
    raise RuntimeError(f"FRED fetch failed: {series_id}")


def yahoo(ticker, start=dt.datetime(1985, 1, 1), interval="1mo", retries=3):
    """Yahoo chart API -> pd.Series of closes indexed by PeriodIndex('M')."""
    p1 = int(start.timestamp()); p2 = int(time.time())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={p1}&period2={p2}&interval={interval}")
    for a in range(retries):
        try:
            r = requests.get(url, timeout=45, headers=HDR)
            if r.status_code == 200:
                res = r.json()["chart"]["result"][0]
                ts = res["timestamp"]; cl = res["indicators"]["quote"][0]["close"]
                s = pd.Series({pd.Timestamp(t, unit="s").to_period("M"): c
                               for t, c in zip(ts, cl) if c is not None})
                s = s[~s.index.duplicated(keep="last")].sort_index()
                if len(s):
                    return s
        except Exception:
            pass
        time.sleep(1 + a)
    raise RuntimeError(f"Yahoo fetch failed: {ticker}")


def yahoo_daily(ticker, start, retries=3):
    """Daily closes -> dict 'YYYY-MM-DD' -> close."""
    p1 = int(start.timestamp()); p2 = int(time.time())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1={p1}&period2={p2}&interval=1d")
    for a in range(retries):
        try:
            r = requests.get(url, timeout=45, headers=HDR)
            if r.status_code == 200:
                res = r.json()["chart"]["result"][0]
                ts = res["timestamp"]; cl = res["indicators"]["quote"][0]["close"]
                return {dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"): c
                        for t, c in zip(ts, cl) if c is not None}
        except Exception:
            pass
        time.sleep(1 + a)
    return {}


def yahoo_fundamentals(symbol, fields, retries=2):
    base = "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/"
    p1 = int(dt.datetime(2018, 1, 1).timestamp()); p2 = int(time.time())
    url = f"{base}{symbol}?symbol={symbol}&type={','.join(fields)}&period1={p1}&period2={p2}"
    for a in range(retries):
        try:
            r = requests.get(url, timeout=40, headers=HDR)
            if r.status_code == 200:
                out = {}
                for item in r.json()["timeseries"]["result"]:
                    key = item.get("meta", {}).get("type", [None])[0]
                    if key and key in item:
                        for v in item[key]:
                            if v:
                                out.setdefault(key, {})[v["asOfDate"][:4]] = v["reportedValue"]["raw"]
                return out
        except Exception:
            pass
        time.sleep(1 + a)
    return {}


# ------------------------------------------------------------------- transforms
def z(s):
    s = pd.Series(s).astype(float)
    sd = s.std()
    return (s - s.mean()) / (sd if sd else 1.0)


def to_list(s, index, nd=4):
    """Reindex a Series onto `index` and emit a JSON-safe list with None for NaN."""
    s = s.reindex(index)
    return [None if pd.isna(v) else round(float(v), nd) for v in s.values]


def period_index(dates):
    """Dashboard date strings -> PeriodIndex('M'). Handles YYYY-MM and YYYY-MM-DD."""
    return pd.PeriodIndex([pd.Period(d[:7], "M") for d in dates], freq="M")


def leadlag(sig, tgt, kmax=24):
    df = pd.concat([pd.Series(sig).rename("s"), pd.Series(tgt).rename("t")], axis=1).dropna()
    if len(df) < 24:
        return 0, 0.0
    out = {k: df["s"].corr(df["t"].shift(-k)) for k in range(0, kmax + 1)}
    kb = max(out, key=lambda k: (out[k] if pd.notna(out[k]) else -9))
    return kb, round(float(out[kb]), 4)


def fwd_ic(sig, price, h):
    fwd = 100 * (price.shift(-h) / price - 1)
    df = pd.concat([pd.Series(sig), fwd], axis=1).dropna()
    if len(df) < 24:
        return None
    return round(float(df.iloc[:, 0].corr(df.iloc[:, 1])), 3)


def log(msg):
    print(f"[{dt.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)
