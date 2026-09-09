"""Refresh the Commodity Demand Lead Index.

  index = 0.60 * global growth LEI  +  0.40 * China credit impulse   (standardised)

Weights were fixed by maximising correlation with FORWARD commodity returns
(3-12m). Growth momentum alone is near-coincident with commodity prices; the
credit impulse supplies the genuine forward lead.

The six national growth LEIs come from data/international-growth-leading-indicators.html
(a build artefact of the separate growth-LEI project). That file is a STATIC input
here: re-export it from that project and drop it in to move the LEI block forward.
Everything else is re-fetched live.
"""
import re, json
import pandas as pd
from common import (DASH, DATA, log, extract_payload, inject_payload, fred, z,
                    to_list, today_str, leadlag)

PATH = f"{DASH}/commodity_demand_lead_index.html"
LEI_FILE = f"{DATA}/international-growth-leading-indicators.html"
START = pd.Period("1995-01", "M")

LEI_W = {"CN": 0.45, "US": 0.22, "EA": 0.16, "JP": 0.09, "UK": 0.05, "AU": 0.03}
CLI_W = {"CHNLOLITOAASTSAM": 0.42, "USALOLITOAASTSAM": 0.16, "DEULOLITOAASTSAM": 0.12,
         "JPNLOLITOAASTSAM": 0.07, "INDLOLITOAASTSAM": 0.08, "KORLOLITOAASTSAM": 0.04,
         "BRALOLITOAASTSAM": 0.05, "AUSLOLITOAASTSAM": 0.03, "GBRLOLITOAASTSAM": 0.03}
W_LEI, W_CREDIT = 0.60, 0.40


def load_country_leis():
    html = open(LEI_FILE, encoding="utf-8").read()
    m = re.search(r"\bDATA\s*=\s*\{", html)
    start = html.index("{", m.start()); depth = 0; instr = False; esc = False
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
                    D = json.loads(html[start:j + 1]); break
    out = {}
    for c in LEI_W:
        comp = D[c]["composite"]
        out[c] = pd.Series({pd.Period(d[:7], "M"): v for d, v in zip(comp["d"], comp["v"])}).sort_index()
    return out, {c: D["names"][c] for c in LEI_W}


def main():
    log("Demand: loading country growth LEIs (static input)")
    country, names = load_country_leis()
    lei_df = pd.DataFrame(country); wl = pd.Series(LEI_W)
    lei_glob = z(((lei_df * wl).sum(axis=1) / wl.sum()).dropna())

    log("Demand: fetching China credit impulse (BIS)")
    cg = fred("QCNPAM770A")                     # credit to private non-fin, % of GDP
    imp_q = cg.diff(4)                          # 1-year change = credit impulse
    imp = imp_q.reindex(pd.period_range(cg.index.min(), cg.index.max(), freq="M")).interpolate()
    credit = z(imp)

    log("Demand: fetching cross-checks and targets")
    kx = fred("XTEXVA01KRM667S")
    korea = z((100 * (kx / kx.shift(12) - 1)).rolling(3).mean())
    cli_df = pd.DataFrame({s: z(fred(s)) for s in CLI_W}); wc = pd.Series(CLI_W)
    cli_glob = z(((cli_df * wc).sum(axis=1) / wc.sum()).dropna())

    tgt = {}
    for key, sid in {"all": "PALLFNFINDEXM", "metals": "PMETAINDEXM",
                     "energy": "PNRGINDEXM", "indu": "PINDUINDEXM"}.items():
        p = fred(sid); tgt[key] = 100 * (p / p.shift(12) - 1)

    idx = pd.period_range(START, max(lei_glob.dropna().index[-1], credit.dropna().index[-1]), freq="M")
    comp = z((W_LEI * lei_glob.reindex(idx) + W_CREDIT * credit.reindex(idx).ffill()).dropna())

    var, P, s, e = extract_payload(PATH)
    P["dates"] = [str(p) for p in idx]
    P["composite"] = to_list(comp, idx)
    P["targets"] = {k: to_list(v, idx) for k, v in tgt.items()}
    P["components"] = {
        "GlobalLEI": to_list(lei_glob, idx),
        "ChinaCreditImpulse": to_list(credit.reindex(idx).ffill(), idx),
        "GlobalTradePulse": to_list(korea, idx),
        "OECD_CLI": to_list(cli_glob, idx),
        "ChinaLEI": to_list(z(country["CN"]), idx),
    }
    P["countries"] = {c: to_list(z(country[c]), idx) for c in LEI_W}
    P["countryNames"] = names
    P["cweights"] = LEI_W
    kb, rb = leadlag(comp.reindex(idx), tgt["all"].reindex(idx))
    P["meta"].update(updated=today_str(), start=str(idx[0]), end=str(idx[-1]),
                     weights={"GlobalLEI": W_LEI, "ChinaCreditImpulse": W_CREDIT,
                              "GlobalTradePulse": 0.0},
                     leadPeak=int(kb), leadR=rb)
    inject_payload(PATH, P, s, e)
    log(f"Demand: rebuilt through {idx[-1]} (index={P['composite'][-1]}, lead {kb}m r={rb})")


if __name__ == "__main__":
    main()
