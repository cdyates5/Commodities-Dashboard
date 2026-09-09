"""Refresh the two-driver Supply + Demand model.

  supply  = z(mean[ -z(capex/assets), z(D&A/assets), z(ROA) ])   <- genuine capital
            cycle from the Census QFR (same engine as the pure supply model)
  demand  = z(mean of four standardised 12-month impulses:
              EM equities, HY credit, inverted US dollar, 10-year yield change)
  target  = S&P GSCI, percent deviation from its 36-month moving average

The dashboard re-mixes supply and demand in-browser from the sub-component
arrays, so this script only has to keep those arrays current.
"""
import datetime as dt
import numpy as np
import pandas as pd
from common import (DASH, log, extract_payload, inject_payload, fred, yahoo, z,
                    to_list, today_str)
from refresh_supply import sector_ratios

PATH = f"{DASH}/commodity_supply_demand_model.html"
START = pd.Period("2003-01", "M")


def main():
    log("Supply+Demand: supply leg from QFR")
    ca, da, roa = sector_ratios()
    sub_supply = {
        "Capex/assets (inv.)": z(-ca),
        "D&A/assets": z(da),
        "Return on assets": z(roa),
    }

    log("Supply+Demand: demand leg from market data")
    eem = yahoo("EEM", dt.datetime(2000, 1, 1))
    hyg = yahoo("HYG", dt.datetime(2000, 1, 1))
    dxy = yahoo("DX-Y.NYB", dt.datetime(1995, 1, 1))
    tnx = yahoo("^TNX", dt.datetime(1995, 1, 1))
    sub_demand = {
        "EM equities (12m)": z(100 * (eem / eem.shift(12) - 1)),
        "HY credit (12m)": z(100 * (hyg / hyg.shift(12) - 1)),
        "US dollar (inv,12m)": z(-(100 * (dxy / dxy.shift(12) - 1))),
        "Rates impulse (10y 12m)": z((tnx - tnx.shift(12)) * 0.5),
    }

    log("Supply+Demand: target and copper/gold")
    gsci = yahoo("^SPGSCI", dt.datetime(1995, 1, 1))
    detrend = 100 * (gsci / gsci.rolling(36, min_periods=18).mean() - 1)
    try:
        cu = yahoo("HG=F", dt.datetime(1995, 1, 1)); au = yahoo("GC=F", dt.datetime(1995, 1, 1))
        coppergold = z((cu / au).dropna())
    except Exception:
        coppergold = pd.Series(dtype=float)

    idx = pd.period_range(START, detrend.dropna().index[-1], freq="M")
    supply = z(pd.concat([sub_supply[k].reindex(idx) for k in sub_supply], axis=1).mean(axis=1))
    demand = z(pd.concat([sub_demand[k].reindex(idx) for k in sub_demand], axis=1).mean(axis=1))

    var, P, s, e = extract_payload(PATH)
    P["series"] = {
        "dates": [str(p) for p in idx],
        "detrend": to_list(detrend, idx),
        "price": to_list(gsci, idx, nd=2),
        "supply": to_list(supply, idx),
        "demand": to_list(demand, idx),
        "coppergold": to_list(coppergold, idx) if len(coppergold) else P["series"]["coppergold"],
        "supply_sub": {k: to_list(v, idx) for k, v in sub_supply.items()},
        "demand_sub": {k: to_list(v, idx) for k, v in sub_demand.items()},
    }
    P["meta"]["updated"] = today_str()
    P["meta"]["lastDate"] = str(idx[-1])
    P["meta"]["nMonths"] = len(idx)
    inject_payload(PATH, P, s, e)
    log(f"Supply+Demand: rebuilt through {idx[-1]} "
        f"(supply={P['series']['supply'][-1]}, demand={P['series']['demand'][-1]})")


if __name__ == "__main__":
    main()
