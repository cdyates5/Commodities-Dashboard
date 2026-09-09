"""Refresh the Supply / capex-cycle model.

Capex is reconstructed from the Census Quarterly Financial Report (All Mining)
balance sheet, because multi-decade Capex/Assets fundamentals are not published
directly:

  capex(TTM)      = d(Net PP&E, 4 quarters) + TTM depreciation
  capex/assets    = 100 * capex / total assets, 3-quarter smoothed, floored at 0
  D&A/assets      = 100 * TTM depreciation / total assets
  ROA             = 100 * TTM income / total assets
  scarcity        = z(mean[ -z(capex/assets), z(D&A/assets), z(ROA) ])

Quarterly series are interpolated to monthly. Targets are the IMF all-commodity
and energy indices as 2-year percent change.
"""
import pandas as pd
from common import (DASH, log, extract_payload, inject_payload, fred, z,
                    to_list, today_str, yahoo_fundamentals)
import numpy as np

PATH = f"{DASH}/commodity_supply_capex_cycle.html"
START = pd.Period("2001-01", "M")

QFR = {"assets": "QFR223MINUSNO", "deprec": "QFR102MINUSNO",
       "netppe": "QFR219MINUSNO", "income": "QFR104MINUSNO"}

BASKETS = {
    "Oil & Gas": ["XOM", "CVX", "COP", "EOG", "OXY", "DVN", "FANG", "CTRA",
                  "APA", "MPC", "PSX", "VLO", "WMB", "KMI", "OKE", "HES"],
    "Energy Equip & Services": ["SLB", "HAL", "BKR", "NOV", "FTI", "WFRD", "RIG", "HP", "PTEN"],
    "Metals & Mining": ["BHP", "RIO", "VALE", "FCX", "SCCO", "NEM", "GOLD", "NUE",
                        "STLD", "TECK", "AA", "CLF", "MP"],
}
FIELDS = ["annualCapitalExpenditure", "annualTotalAssets",
          "annualReconciledDepreciation", "annualEBIT", "annualInvestedCapital"]


def q2m(s):
    s = s.dropna(); s.index = s.index.to_timestamp()
    m = s.resample("MS").interpolate("linear")
    m.index = m.index.to_period("M")
    return m


def sector_ratios():
    d = {k: fred(v) for k, v in QFR.items()}
    dep_ttm = d["deprec"].rolling(4).sum()
    inc_ttm = d["income"].rolling(4).sum()
    capex_q = d["netppe"].diff(4) + dep_ttm
    ca = (100 * capex_q / d["assets"]).rolling(3).mean().clip(lower=0)
    da = 100 * dep_ttm / d["assets"]
    roa = 100 * inc_ttm / d["assets"]
    return q2m(ca), q2m(da), q2m(roa)


def company_table():
    rows = []
    for ind, syms in BASKETS.items():
        for sym in syms:
            f = yahoo_fundamentals(sym, FIELDS)
            if not f:
                continue
            def latest(key):
                if key not in f or not f[key]:
                    return np.nan
                return f[key][sorted(f[key])[-1]]
            def yr(key):
                if key not in f or not f[key]:
                    return None
                return sorted(f[key])[-1]
            rows.append(dict(industry=ind, year=yr("annualTotalAssets"),
                             capex=latest("annualCapitalExpenditure"),
                             assets=latest("annualTotalAssets"),
                             da=latest("annualReconciledDepreciation"),
                             ebit=latest("annualEBIT"), ic=latest("annualInvestedCapital")))
    df = pd.DataFrame(rows).dropna(subset=["capex", "assets"])
    if df.empty:
        return None, None
    df["CapexToAssets"] = df["capex"].abs() / df["assets"]
    df["DAToAssets"] = df["da"] / df["assets"]
    df["ROIC"] = df["ebit"] * (1 - 0.21) / df["ic"]
    for c in ["CapexToAssets", "DAToAssets", "ROIC"]:
        df.loc[~np.isfinite(df[c]), c] = np.nan
        lo, hi = df[c].quantile([.02, .98])
        df[c] = df[c].clip(lo, hi)
    df["scarcity"] = pd.concat([z(-df["CapexToAssets"]), z(df["DAToAssets"]), z(df["ROIC"])],
                               axis=1).mean(axis=1)
    out = []
    for ind, g in df.groupby("industry"):
        w = g["assets"]
        out.append({"industry": ind, "n": int(len(g)),
                    "capexToAssets": round(float(np.average(g["CapexToAssets"], weights=w)), 4),
                    "daToAssets": round(float(np.average(g["DAToAssets"], weights=w)), 4),
                    "roic": round(float(np.average(g["ROIC"], weights=w)), 4),
                    "scarcity": round(float(np.average(g["scarcity"], weights=w)), 3)})
    fy = int(pd.to_numeric(df["year"], errors="coerce").dropna().max())
    return out, fy


def main():
    log("Supply: fetching QFR sector accounts")
    ca, da, roa = sector_ratios()
    scar = z(pd.concat([-z(ca), z(da), z(roa)], axis=1).mean(axis=1))

    log("Supply: fetching commodity targets")
    allc = fred("PALLFNFINDEXM"); en = fred("PNRGINDEXM")
    com2y_all = 100 * (allc / allc.shift(24) - 1)
    com2y_en = 100 * (en / en.shift(24) - 1)

    idx = pd.period_range(START, max(com2y_all.dropna().index[-1], ca.dropna().index[-1]), freq="M")

    var, P, s, e = extract_payload(PATH)
    P["series"] = {
        "dates": [str(p) for p in idx],
        "com2y_all": to_list(com2y_all, idx),
        "com2y_energy": to_list(com2y_en, idx),
        "capex_assets": to_list(ca, idx),
        "da_assets": to_list(da, idx),
        "roa": to_list(roa, idx),
        "scarcity": to_list(scar, idx),
    }
    log("Supply: refreshing live company fundamentals")
    table, fy = company_table()
    if table:
        P["fundamentals"] = table
        P["meta"]["fundamentalFY"] = fy
    P["meta"]["updated"] = today_str()
    P["meta"]["lastDate"] = str(idx[-1])
    ce = [d for d, v in zip(P["series"]["dates"], P["series"]["capex_assets"]) if v is not None]
    if ce:
        P["meta"]["capexSeriesEnd"] = ce[-1]
    inject_payload(PATH, P, s, e)
    log(f"Supply: rebuilt through {idx[-1]} (scarcity={P['series']['scarcity'][-1]})")


if __name__ == "__main__":
    main()
