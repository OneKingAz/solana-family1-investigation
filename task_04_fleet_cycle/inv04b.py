"""Task 04 v2 (analyst's corrections, 18.11): no overlapping windows. Each return series and each funding wave is attributed only to the
nearest PRECEDING pool event; waves are reported as their own events with exact slots. Separates the 9 «29-SOL, buy-only» wallets.
NO RPC. Out: investigation_task_04/ return_series.csv, funding_waves.csv, nine_wallets.csv, _v2.json"""
import collections, csv, datetime as dt, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
O = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04"
GC = "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
EXPORT_END = "2026-11-17T17:06:20Z"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
W = {r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_03\park_wallet_flows.csv")}
T = [r for r in rd(os.path.join(A, "sol_export_transfers.csv")) if r["asset"] == "SOL" and r["in_trade"] != "True"]
P = rd(os.path.join(O, "gekko_pools.csv"))
cyc = {r["wallet"]: r for r in rd(os.path.join(O, "wallet_cycle.csv"))}
to_u = lambda s: int(dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()) if s else None
events = []
for p in P:
    events.append((to_u(p["create_utc"]), "создание", p["pool"]))
    if p["first_withdraw_utc"]:
        events.append((to_u(p["first_withdraw_utc"]), "первая транзакция вывода", p["pool"]))
    if p["main_withdraw_after_min_sol_pools"]:
        events.append((to_u(p["create_utc"]) + round(float(p["main_withdraw_after_min_sol_pools"]) * 60), "основной вывод (sol_pools, ±1 мин)", p["pool"]))
events.sort()


def series(rows, gap=60):
    """group transfers into series: a new series when the next transfer is > gap s after the previous one"""
    rows = sorted(rows, key=lambda r: int(r["slot"]))
    out, cur = [], []
    for r in rows:
        if cur and int(r["blockTime"]) - int(cur[-1]["blockTime"]) > gap:
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def prev_event(u):
    ev = [e for e in events if e[0] <= u]
    return ev[-1] if ev else None


def next_event(u):
    ev = [e for e in events if e[0] > u]
    return ev[0] if ev else None


def describe(rows, label):
    res = []
    for s in series(rows):
        t0, t1 = int(s[0]["blockTime"]), int(s[-1]["blockTime"])
        pe, ne = prev_event(t0), next_event(t0)
        amts = collections.Counter(round(float(r["amount"]), 6) for r in s)
        res.append(dict(kind=label, transfers=len(s), wallets=len({r["source"] if label == "возврат" else r["destination"] for r in s}),
                        start_utc=iso(t0), end_utc=iso(t1), slot_first=s[0]["slot"], slot_last=s[-1]["slot"], sol=round(sum(float(r["amount"]) for r in s), 6),
                        common_amounts=" ".join(f"{a}×{n}" for a, n in amts.most_common(3)),
                        previous_event=f"{pe[1]} {pe[2][:8]} {iso(pe[0])} (за {t0 - pe[0]} с)" if pe else "",
                        next_event=f"{ne[1]} {ne[2][:8]} {iso(ne[0])} (через {ne[0] - t0} с)" if ne else ""))
    return res


R = describe([r for r in T if r["destination"] == GC and r["source"] in W], "возврат")
F = describe([r for r in T if r["source"] == GC and r["destination"] in W], "пополнение")
for name, rows in (("return_series.csv", R), ("funding_waves.csv", F)):
    with open(os.path.join(O, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)
# second-series wallets ⊂ first?
rs = series([r for r in T if r["destination"] == GC and r["source"] in W])
sub = len({r["source"] for r in rs[1]} - {r["source"] for r in rs[0]}) if len(rs) > 1 else None
# nine wallets: buy-only in GEKKO pool
nine = [w_ for w_, c in cyc.items() if int(c["sells"]) == 0]
nrows = []
for w_ in sorted(nine):
    fin = [r for r in T if r["source"] == GC and r["destination"] == w_]
    nrows.append(dict(wallet=w_, funded_sol=round(sum(float(r["amount"]) for r in fin), 6), funded_n=len(fin),
                      funded_amounts=" ".join(sorted({str(round(float(r["amount"]), 4)) for r in fin})),
                      returned_sol=cyc[w_]["returned_sol"], buys=cyc[w_]["buys"], buy_sol=cyc[w_]["buy_sol"], sells=cyc[w_]["sells"],
                      first_funding_utc=iso(min(int(r["blockTime"]) for r in fin)), last_funding_utc=iso(max(int(r["blockTime"]) for r in fin))))
with open(os.path.join(O, "nine_wallets.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(nrows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(nrows)
json.dump(dict(returns=R, fundings=F, second_not_in_first=sub, nine=nrows, export_end=EXPORT_END), open(os.path.join(O, "_v2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in R:
    print("ВОЗВРАТ", r)
for r in F:
    print("ПОПОЛНЕНИЕ", {k: r[k] for k in ("transfers", "wallets", "start_utc", "end_utc", "sol", "common_amounts", "previous_event", "next_event")})
print("второй серии кошельков вне первой:", sub)
for r in nrows:
    print("9:", r)
