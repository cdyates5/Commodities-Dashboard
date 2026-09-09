"""Refresh the two CFTC positioning monitors (managed money + non-commercial).

Methodology was reverse-engineered and validated against the full baked history
(mean absolute error 0.00 on every basket):

  managed money   : 100 * sum(long - short) / sum(long + short)   [disaggregated, futures-only]
  non-commercial  : 100 * sum(long - short) / sum(open interest)  [legacy, futures-only]

Both are UNWEIGHTED sums across the basket constituents. The `weights` block in
each payload applies only to the notional price overlay, not the positioning.

New weeks are APPENDED, so previously validated history is never rewritten.
"""
import datetime as dt
import json
import requests
from common import DASH, HDR, log, extract_payload, inject_payload, yahoo_daily

CODES = {
    "WTI Crude": "067651", "Natural Gas": "023651", "RBOB Gasoline": "111659",
    "Heating Oil/ULSD": "022651", "Gold": "088691", "Silver": "084691",
    "Copper": "085692", "Platinum": "076651", "Palladium": "075651",
    "Corn": "002602", "Soybeans": "005602", "Soybean Oil": "007601",
    "Soybean Meal": "026603", "Wheat SRW": "001602", "Wheat HRW": "001612",
    "Wheat HRS": "001626", "Sugar #11": "080732", "Coffee": "083731",
    "Cocoa": "073732", "Cotton": "033661", "Live Cattle": "057642",
    "Lean Hogs": "054642", "Feeder Cattle": "061641",
}
YF = {
    "WTI Crude": "CL=F", "Natural Gas": "NG=F", "RBOB Gasoline": "RB=F",
    "Heating Oil/ULSD": "HO=F", "Gold": "GC=F", "Silver": "SI=F", "Copper": "HG=F",
    "Platinum": "PL=F", "Palladium": "PA=F", "Corn": "ZC=F", "Soybeans": "ZS=F",
    "Soybean Oil": "ZL=F", "Soybean Meal": "ZM=F", "Wheat SRW": "ZW=F",
    "Wheat HRW": "KE=F", "Wheat HRS": "MW=F", "Sugar #11": "SB=F", "Coffee": "KC=F",
    "Cocoa": "CC=F", "Cotton": "CT=F", "Live Cattle": "LE=F", "Lean Hogs": "HE=F",
    "Feeder Cattle": "GF=F",
}
BASK = {
    "Energy": ["WTI Crude", "Natural Gas", "RBOB Gasoline", "Heating Oil/ULSD"],
    "Metals": ["Gold", "Silver", "Copper", "Platinum", "Palladium"],
    "Agriculture": ["Corn", "Soybeans", "Soybean Oil", "Soybean Meal", "Wheat SRW",
                    "Wheat HRW", "Wheat HRS", "Sugar #11", "Coffee", "Cocoa",
                    "Cotton", "Live Cattle", "Lean Hogs", "Feeder Cattle"],
}
BASK["All"] = BASK["Energy"] + BASK["Metals"] + BASK["Agriculture"]

DISAGG = "72hh-3qpy"   # CFTC disaggregated futures-only
LEGACY = "6dca-aqww"   # CFTC legacy futures-only


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch_cot(dataset, cols, date_from):
    codes = "','".join(CODES.values())
    where = (f"report_date_as_yyyy_mm_dd >= '{date_from}T00:00:00' "
             f"AND cftc_contract_market_code in ('{codes}')")
    url = (f"https://publicreporting.cftc.gov/resource/{dataset}.json"
           f"?$where={requests.utils.quote(where)}&$limit=20000"
           f"&$select=report_date_as_yyyy_mm_dd,cftc_contract_market_code,{cols}")
    rows = requests.get(url, timeout=90, headers=HDR).json()
    book = {}
    lc, sc, oc = cols.split(",")
    for r in rows:
        d = r["report_date_as_yyyy_mm_dd"][:10]
        book.setdefault(d, {})[r["cftc_contract_market_code"]] = (
            _num(r.get(lc)), _num(r.get(sc)), _num(r.get(oc)))
    return book


def basket_value(book, date, basket, mode):
    net = den = 0.0
    for c in BASK[basket]:
        rec = book.get(date, {}).get(CODES[c])
        if not rec or rec[0] is None or rec[1] is None:
            continue
        net += rec[0] - rec[1]
        den += (rec[0] + rec[1]) if mode == "LS" else (rec[2] or 0)
    return round(100 * net / den, 2) if den else None


def _price_on(series, d, back=9):
    for k in range(back):
        dd = (dt.datetime.strptime(d, "%Y-%m-%d") - dt.timedelta(days=k)).strftime("%Y-%m-%d")
        if dd in series:
            return series[dd]
    return None


def refresh(filename, dataset, cols, mode):
    path = f"{DASH}/{filename}"
    var, P, s, e = extract_payload(path)
    last = max(P["categories"][b]["date"][-1] for b in P["categories"])
    since = (dt.datetime.strptime(last, "%Y-%m-%d") - dt.timedelta(days=10)).strftime("%Y-%m-%d")

    book = fetch_cot(dataset, cols, since)
    new_dates = sorted(d for d in book if d > last)
    if not new_dates:
        log(f"{filename}: already current at {last}")
        return 0

    # price overlay inputs
    px = {c: yahoo_daily(t, dt.datetime.strptime(since, "%Y-%m-%d") - dt.timedelta(days=20))
          for c, t in YF.items()}
    gsci = yahoo_daily("^SPGSCI", dt.datetime.strptime(since, "%Y-%m-%d") - dt.timedelta(days=20))

    added = 0
    for b in ["All", "Energy", "Metals", "Agriculture"]:
        cat = P["categories"][b]; W = P["weights"][b]
        prev = cat["date"][-1]
        for d in [x for x in new_dates if x > cat["date"][-1]]:
            v = basket_value(book, d, b, mode)
            if v is None:
                continue
            cat["date"].append(d)
            cat["mm_net_pct"].append(v)
            # notional-weighted basket return, chained onto the existing index
            num = den = 0.0
            for c in BASK[b]:
                w = W.get(c, 0)
                p0 = _price_on(px.get(c, {}), prev); p1 = _price_on(px.get(c, {}), d)
                if w and p0 and p1 and p0 > 0:
                    num += w * (p1 / p0 - 1); den += w
            ret = (num / den) if den else 0.0
            cat["price_index"].append(round(cat["price_index"][-1] * (1 + ret), 2))
            if "gsci_index" in cat:
                g0 = _price_on(gsci, prev); g1 = _price_on(gsci, d)
                cat["gsci_index"].append(round(cat["gsci_index"][-1] * (g1 / g0), 2)
                                         if g0 and g1 else cat["gsci_index"][-1])
            prev = d; added += 1

    P["meta"]["generated"] = dt.date.today().isoformat()
    P["meta"]["last_date"] = max(P["categories"]["All"]["date"])
    P["meta"]["n_weeks"] = len(P["categories"]["All"]["date"])
    inject_payload(path, P, s, e)
    log(f"{filename}: +{added} basket-weeks -> {P['meta']['last_date']}")
    return added


def main():
    refresh("commodity_positioning_monitor_managed_money.html", DISAGG,
            "m_money_positions_long_all,m_money_positions_short_all,open_interest_all", "LS")
    refresh("commodity_positioning_monitor_speculative.html", LEGACY,
            "noncomm_positions_long_all,noncomm_positions_short_all,open_interest_all", "OI")


if __name__ == "__main__":
    main()
