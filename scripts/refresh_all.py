"""Run every refresh, then rebuild the combined site.

Fault tolerance matters here: if one upstream source is down, the other models
should still publish. Each step is isolated; failures are logged and reported in
the summary, and the build still runs with whatever data is current. The process
exits non-zero only if EVERY refresh failed (a real outage) or the build failed.
"""
import sys, traceback
from common import log
import refresh_positioning, refresh_fci, refresh_supply, refresh_demand, refresh_supply_demand
import build_combined

STEPS = [
    ("positioning (CFTC COT)", refresh_positioning.main),
    ("financial conditions", refresh_fci.main),
    ("supply / capex cycle", refresh_supply.main),
    ("demand lead index", refresh_demand.main),
    ("supply + demand", refresh_supply_demand.main),
]


def main():
    ok, failed = [], []
    for name, fn in STEPS:
        try:
            log(f"--- {name} ---")
            fn()
            ok.append(name)
        except Exception as exc:
            failed.append((name, str(exc)))
            log(f"FAILED {name}: {exc}")
            traceback.print_exc()

    log("--- building combined site ---")
    build_combined.main()

    print("\n=========== REFRESH SUMMARY ===========")
    for n in ok:
        print(f"  OK      {n}")
    for n, e in failed:
        print(f"  FAILED  {n}: {e[:120]}")
    print("=======================================")

    if not ok:
        print("All refreshes failed - treating as an outage.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
