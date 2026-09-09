"""Refresh the Financial Conditions Lead Index (commodities view).

Construction (GMI / Alpine "growth tax"):
  each leg = series - 36m moving average  (level of tightness; YoY changes are
  coincident, the deviation-from-trend carries the lead), standardised, then
  INVERTED so that positive = loose = growth/commodity supportive.

  FCI full = mean(-z(dev DXY), -z(dev GSCI), -z(dev UST10Y))
  FCI ex   = mean(-z(dev DXY), -z(dev UST10Y))   <- no commodity leg (non-circular)

The whole payload is rebuilt each run (all inputs are freely re-fetchable).
"""
import datetime as dt
import pandas as pd
from common import (DASH, log, extract_payload, inject_payload, fred, yahoo,
                    z, to_list, today_str, fwd_ic)

PATH = f"{DASH}/commodity_fci_lead.html"
START = pd.Period("1992-01", "M")


def dev(s, w=36):
    return s - s.rolling(w, min_periods=18).mean()


def main():
    log("FCI: fetching market legs")
    dxy = yahoo("DX-Y.NYB", dt.datetime(1988, 1, 1))
    gsci = yahoo("^SPGSCI", dt.datetime(1988, 1, 1))
    tnx = yahoo("^TNX", dt.datetime(1988, 1, 1))

    tD, tG, tR = z(dev(dxy)), z(dev(gsci)), z(dev(tnx))
    fci_full = z(-pd.concat([tD, tG, tR], axis=1).mean(axis=1))
    fci_exc = z(-pd.concat([tD, tR], axis=1).mean(axis=1))

    log("FCI: fetching commodity targets")
    p_all = fred("PALLFNFINDEXM")
    p_met = fred("PMETAINDEXM")
    y_all = 100 * (p_all / p_all.shift(12) - 1)
    y_met = 100 * (p_met / p_met.shift(12) - 1)

    idx = pd.period_range(START, fci_full.dropna().index[-1], freq="M")

    var, P, s, e = extract_payload(PATH)
    P["dates"] = [str(p) for p in idx]
    P["fci_full"] = to_list(fci_full, idx)
    P["fci_exc"] = to_list(fci_exc, idx)
    P["legs"] = {"dollar": to_list(-tD, idx),
                 "commodity": to_list(-tG, idx),
                 "rates": to_list(-tR, idx)}
    P["targets"] = {"all": to_list(y_all, idx), "metals": to_list(y_met, idx)}
    P["fwdic"] = {
        "full_all": [fwd_ic(fci_full, p_all, h) for h in range(1, 25)],
        "full_met": [fwd_ic(fci_full, p_met, h) for h in range(1, 25)],
        "exc_all": [fwd_ic(fci_exc, p_all, h) for h in range(1, 25)],
        "exc_met": [fwd_ic(fci_exc, p_met, h) for h in range(1, 25)],
    }
    P["meta"]["updated"] = today_str()
    P["meta"]["start"] = str(idx[0]); P["meta"]["end"] = str(idx[-1])
    inject_payload(PATH, P, s, e)
    log(f"FCI: rebuilt through {idx[-1]} (FCI={P['fci_full'][-1]})")


if __name__ == "__main__":
    main()
