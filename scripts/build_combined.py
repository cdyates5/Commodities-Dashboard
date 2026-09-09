"""Assemble the seven dashboards into one published page (site/index.html).

Each dashboard is fully self-contained, so it is embedded base64 into its own
isolated iframe. That avoids CSS/JS collisions between independently-styled
builds and lets each keep its exact validated behaviour.
"""
import base64, os, datetime as dt
from common import DASH, SITE, log

TABS = [
    ("sd", "commodity_supply_demand_model.html", "Supply + Demand",
     "Two-driver model. <b>Supply</b> (the genuine capital cycle) and <b>demand</b> "
     "(a growth &amp; liquidity index) combined into one signal that leads commodity prices."),
    ("sup", "commodity_supply_capex_cycle.html", "Supply &middot; capex cycle",
     "Pure supply model. Producer <b>Capex / Total Assets</b> &mdash; inverted and read forward "
     "&mdash; with the three-ratio capital-scarcity read."),
    ("dem", "commodity_demand_lead_index.html", "Demand &middot; lead index",
     "Pure demand model. A commodity-weighted <b>global growth LEI</b> plus the "
     "<b>China credit impulse</b> &mdash; the demand-side lead for commodity prices."),
    ("fci", "commodity_fci_lead.html", "Fin. conditions &middot; lead",
     "Financial-conditions model. The growth-tax composite &mdash; <b>dollar, commodities and "
     "rates</b> as deviations from trend, inverted &mdash; leads commodity prices by ~13 months."),
    ("con", "commodity_contango_index.html", "Contango &middot; carry",
     "Carry model. The energy-complex <b>term structure</b> &mdash; front vs deferred, annualised "
     "%/yr &mdash; as a contango/backwardation signal, with a live cross-section."),
    ("posmm", "commodity_positioning_monitor_managed_money.html", "Positioning &middot; money managers",
     "Positioning model. CFTC <b>managed-money</b> net length across the futures complex, by "
     "basket, with percentile bands &mdash; a contrarian read on crowding."),
    ("posnc", "commodity_positioning_monitor_speculative.html", "Positioning &middot; speculative",
     "Positioning model. Legacy <b>non-commercial</b> (total speculative) net length across the "
     "complex, by basket, with percentile bands."),
]

SHELL = r"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Acheron — Commodity Capital Cycle</title>
<style>
:root{--ink:#16181D;--paper:#F4F1EA;--red:#C8102E;--line:#E2DECF;--muted:#6E6C64;--soft:#96938A}
*{box-sizing:border-box}
html,body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.topbar{position:sticky;top:0;z-index:50;background:rgba(244,241,234,.93);backdrop-filter:saturate(1.2) blur(8px);border-bottom:1px solid var(--line);}
.tbin{max-width:1200px;margin:0 auto;padding:11px 22px;display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.brand{display:flex;align-items:baseline;gap:10px;min-width:0}
.brand .mk{font-family:Georgia,serif;font-weight:600;font-size:16px;letter-spacing:-.01em}
.brand .mk b{color:var(--red)}
.brand .sub{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--soft);white-space:nowrap}
.seg{display:inline-flex;background:#ECE8DC;border:1px solid var(--line);border-radius:9px;padding:3px;flex-wrap:wrap;gap:1px}
.seg button{font:inherit;font-size:11.5px;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 10px;border-radius:7px;cursor:pointer;transition:.14s;white-space:nowrap}
.seg button:hover{color:var(--ink)}
.seg button.active{background:var(--ink);color:#fff;box-shadow:0 1px 3px rgba(20,20,15,.18)}
.desc{max-width:1200px;margin:0 auto;padding:9px 22px 0;font-size:12.5px;color:var(--muted);line-height:1.5}
.stamp{max-width:1200px;margin:0 auto;padding:4px 22px 0;font-size:11px;color:var(--soft)}
.frame-wrap{position:relative;max-width:1200px;margin:0 auto;padding:0 6px}
iframe{width:100%;border:0;display:block;background:transparent;position:absolute;top:0;left:0;visibility:hidden;padding:0 20px}
iframe.active{position:relative;visibility:visible}
@media(max-width:1000px){.brand .sub{display:none}.seg button{padding:6px 8px;font-size:11px}}
</style></head><body>
<div class="topbar"><div class="tbin">
  <div class="brand"><span class="mk">Acheron <b>&middot;</b> Commodity Capital Cycle</span><span class="sub">Systematic macro</span></div>
  <div class="seg" id="seg">
    __BTNS__
  </div>
</div><div class="desc" id="desc"></div><div class="stamp">Data refreshed __STAMP__ UTC</div></div>
<div class="frame-wrap">
  __IFR__
</div>
<script>
const DOC={__DOC__};
const DESC={__DESC__};
function b64ToStr(b){const bin=atob(b);const u=Uint8Array.from(bin,c=>c.charCodeAt(0));return new TextDecoder("utf-8").decode(u);}
const frames={__FRAMES__};
function autoHeight(f){try{const h=f.contentDocument.body.scrollHeight;if(h>50)f.style.height=(h+24)+"px";}catch(e){}}
Object.entries(frames).forEach(([k,f])=>{
  f.addEventListener("load",()=>{autoHeight(f);setTimeout(()=>autoHeight(f),400);setTimeout(()=>autoHeight(f),1200);
    try{const ro=new ResizeObserver(()=>autoHeight(f));ro.observe(f.contentDocument.body);}catch(e){}});
  f.srcdoc=b64ToStr(DOC[k]);});
function show(v){
  document.querySelectorAll("#seg button").forEach(x=>x.classList.toggle("active",x.dataset.v===v));
  Object.entries(frames).forEach(([k,f])=>f.classList.toggle("active",k===v));
  document.getElementById("desc").innerHTML=DESC[v];const f=frames[v];
  setTimeout(()=>{try{f.contentWindow.dispatchEvent(new Event("resize"));}catch(e){}autoHeight(f);},40);
  setTimeout(()=>autoHeight(f),350);setTimeout(()=>autoHeight(f),900);}
document.querySelectorAll("#seg button").forEach(b=>b.addEventListener("click",()=>show(b.dataset.v)));
document.getElementById("desc").innerHTML=DESC.sd;
window.addEventListener("resize",()=>Object.values(frames).forEach(autoHeight));
</script></body></html>"""


def main():
    os.makedirs(SITE, exist_ok=True)
    b64 = {}
    for key, fn, _, _ in TABS:
        p = os.path.join(DASH, fn)
        if not os.path.exists(p):
            log(f"WARNING: missing {fn}, skipping tab")
            continue
        b64[key] = base64.b64encode(open(p, "rb").read()).decode()
    tabs = [t for t in TABS if t[0] in b64]
    btns = "\n    ".join(
        f'<button data-v="{k}"{" class=\"active\"" if i == 0 else ""}>{lab}</button>'
        for i, (k, _, lab, _) in enumerate(tabs))
    ifr = "\n  ".join(
        f'<iframe id="f-{k}"{" class=\"active\"" if i == 0 else ""} title="{lab}"></iframe>'
        for i, (k, _, lab, _) in enumerate(tabs))
    doc = ",".join(f'{k}:"{b64[k]}"' for k, _, _, _ in tabs)
    desc = ",".join(f'{k}:"{d}"' for k, _, _, d in tabs)
    frames = ",".join(f'{k}:document.getElementById("f-{k}")' for k, _, _, _ in tabs)
    out = (SHELL.replace("__BTNS__", btns).replace("__IFR__", ifr)
           .replace("__DOC__", doc).replace("__DESC__", desc).replace("__FRAMES__", frames)
           .replace("__STAMP__", dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M")))
    dest = os.path.join(SITE, "index.html")
    open(dest, "w", encoding="utf-8").write(out)
    # copy standalone dashboards alongside, so each is directly linkable
    for _, fn, _, _ in tabs:
        src = os.path.join(DASH, fn)
        open(os.path.join(SITE, fn), "w", encoding="utf-8").write(
            open(src, encoding="utf-8").read())
    log(f"built site/index.html ({len(out):,} bytes, {len(tabs)} tabs)")


if __name__ == "__main__":
    main()
