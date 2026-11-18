"""Task 04 (18.11): what the 109 fleet wallets funded by the GEKKO creator DO in the money cycle. NO RPC; sources only read.
Sources (17.11 export, window 2026-11-16T19:19:54Z - 2026-11-17T17:06:20Z): sol_export_trades.csv (swaps with signature, slot, wallet,
side, SOL, pool), sol_export_transfers.csv (SOL transfers; in_trade = False only), sol_export_raw.jsonl.gz (the GEKKO creator's own
CreatePool / Withdraw transactions: pool, slot, time), investigation_task_03/park_wallet_flows.csv (the 109 wallets).
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_04\\ wallet_cycle.csv, cycle_steps.csv, gekko_pools.csv (+ numbers)."""
import bisect, collections, csv, datetime as dt, gzip, json, os, statistics as st, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04"
os.makedirs(OUT, exist_ok=True)
GC = "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
WSOL = "So11111111111111111111111111111111111111112"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if u not in (None, "") else ""
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
med = lambda xs: round(st.median(xs), 2) if xs else ""

W109 = {r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_03\park_wallet_flows.csv")}
TR = [r for r in rd(os.path.join(A, "sol_export_trades.csv")) if r["wallet"] in W109 and not r["err"]]
T = [r for r in rd(os.path.join(A, "sol_export_transfers.csv")) if r["asset"] == "SOL" and r["in_trade"] != "True"]

# GEKKO creator's pools: CreatePool and Withdraw from its own signed transactions
gpools = {}
with gzip.open(os.path.join(A, "sol_export_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        if GC not in line:
            continue
        rec = json.loads(line)
        t = rec["tx"]
        m = t.get("meta") or {}
        ks = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
        if not ks or ks[0] != GC or m.get("err"):
            continue
        logs = " ".join(m.get("logMessages") or [])
        own = collections.defaultdict(set)
        for b in m.get("postTokenBalances") or []:
            own[b.get("owner")].add(b["mint"])
        pool = next((o for o, mm in own.items() if o != GC and WSOL in mm and len(mm) == 2), None)
        if not pool:
            continue
        g = gpools.setdefault(pool, dict(pool=pool, create_slot="", create_unix="", create_sig="", withdraw_slot="", withdraw_unix="", withdraw_sig=""))
        if "CreatePool" in logs:
            g.update(create_slot=t["slot"], create_unix=t["blockTime"], create_sig=rec["signature"])
        elif "Instruction: Withdraw" in logs and not g["withdraw_slot"]:
            g.update(withdraw_slot=t["slot"], withdraw_unix=t["blockTime"], withdraw_sig=rec["signature"])
GPOOL = {p for p, g in gpools.items() if g["create_slot"]}

# ---- per wallet, chronological steps ----
ev = collections.defaultdict(list)  # wallet -> (slot, unix, kind, sol, pool/counterparty, signature)
for r in TR:
    sol = float(r["solAmount"])  # buy < 0, sell > 0
    ev[r["wallet"]].append((int(r["slot"]), int(r["blockTime"]), "buy" if r["side"] == "buy" else "sell", abs(sol), r["pool"], r["signature"]))
for r in T:
    if r["source"] == GC and r["destination"] in W109:
        ev[r["destination"]].append((int(r["slot"]), int(r["blockTime"]), "fund", float(r["amount"]), GC, r["signature"]))
    elif r["destination"] == GC and r["source"] in W109:
        ev[r["source"]].append((int(r["slot"]), int(r["blockTime"]), "return", float(r["amount"]), GC, r["signature"]))
steps, rows = [], []
fund_to_buy, sell_to_return, return_vs_sells, buy_pool_age, buy_in_gpool = [], [], [], [], []
for w in sorted(W109):
    es = sorted(ev[w])
    spent = sum(e[3] for e in es if e[2] == "buy")
    got = sum(e[3] for e in es if e[2] == "sell")
    funded = sum(e[3] for e in es if e[2] == "fund")
    returned = sum(e[3] for e in es if e[2] == "return")
    buys = [e for e in es if e[2] == "buy"]
    g_buys = [e for e in buys if e[4] in GPOOL]
    pools = {e[4] for e in buys}
    # fund -> next buy
    for i, e in enumerate(es):
        if e[2] == "fund":
            nb = next((x for x in es[i + 1:] if x[2] == "buy"), None)
            if nb:
                fund_to_buy.append(nb[1] - e[1])
    # return: sells since the previous return, delay since the last sell
    last_ret = -1
    sells_since = 0.0
    last_sell_t = None
    for e in es:
        if e[2] == "sell":
            sells_since += e[3]
            last_sell_t = e[1]
        elif e[2] == "return":
            if last_sell_t is not None:
                sell_to_return.append(e[1] - last_sell_t)
            return_vs_sells.append((e[3], sells_since))
            sells_since, last_sell_t = 0.0, None
    for e in buys:
        g = gpools.get(e[4])
        if g and g["create_unix"]:
            buy_pool_age.append(e[1] - int(g["create_unix"]))
    buy_in_gpool.append((len(g_buys), len(buys)))
    rows.append(dict(wallet=w, funded_sol=round(funded, 4), returned_sol=round(returned, 4), buys=len(buys), buy_sol=round(spent, 4),
                     sells=sum(1 for e in es if e[2] == "sell"), sell_sol=round(got, 4), trade_result_sol=round(got - spent, 4),
                     pools_traded=len(pools), gekko_pool_buys=len(g_buys), gekko_pool_buy_sol=round(sum(e[3] for e in g_buys), 4),
                     other_pool_buys=len(buys) - len(g_buys), first_event_utc=iso(es[0][1]) if es else "", last_event_utc=iso(es[-1][1]) if es else ""))
    for e in es:
        steps.append(dict(wallet=w, slot=e[0], time_utc=iso(e[1]), step={"fund": "пополнение от GEKKO", "buy": "покупка", "sell": "продажа", "return": "возврат GEKKO"}[e[2]],
                          sol=round(e[3], 9), pool_or_counterparty=e[4], gekko_pool=int(e[4] in GPOOL), signature=e[5]))
with open(os.path.join(OUT, "wallet_cycle.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w_ = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    w_.writeheader()
    w_.writerows(rows)
with open(os.path.join(OUT, "cycle_steps.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w_ = csv.DictWriter(f, fieldnames=list(steps[0].keys()), delimiter=";")
    w_.writeheader()
    w_.writerows(steps)

# ---- per GEKKO pool ----
MAIN_WD = {r["pool"]: r["withdraw_min"] for r in rd(os.path.join(A, "sol_pools.csv"))}  # main withdraw (>60 s after creation, pool > 1 SOL)
prow = []
for p, g in sorted(gpools.items(), key=lambda kv: kv[1]["create_slot"] or 0):
    if not g["create_slot"]:
        continue
    c, wdr = int(g["create_unix"]), (int(g["withdraw_unix"]) if g["withdraw_unix"] else None)
    pb = [r for r in TR if r["pool"] == p]
    b = [r for r in pb if r["side"] == "buy"]
    s = [r for r in pb if r["side"] == "sell"]
    fund_near = [r for r in T if r["source"] == GC and r["destination"] in W109 and c - 600 <= int(r["blockTime"]) <= c + 600]
    ret_after = [r for r in T if r["destination"] == GC and r["source"] in W109 and wdr and wdr <= int(r["blockTime"]) <= wdr + 1800]
    sold_before_wd = sum(abs(float(r["solAmount"])) for r in s if wdr and int(r["blockTime"]) < wdr)
    prow.append(dict(pool=p, create_utc=iso(c), create_slot=g["create_slot"], create_sig=g["create_sig"], first_withdraw_utc=iso(wdr) if wdr else "",
                     first_withdraw_tx_after_min=round((wdr - c) / 60, 1) if wdr else "", first_withdraw_sig=g["withdraw_sig"], main_withdraw_after_min_sol_pools=MAIN_WD.get(p, ""),
                     fleet_wallets_buying=len({r["wallet"] for r in b}), fleet_buys=len(b), fleet_buy_sol=round(sum(abs(float(r["solAmount"])) for r in b), 3),
                     fleet_sells=len(s), fleet_sell_sol=round(sum(abs(float(r["solAmount"])) for r in s), 3), fleet_sell_sol_before_withdraw=round(sold_before_wd, 3),
                     first_fleet_buy_s=min((int(r["blockTime"]) - c for r in b), default=""), median_fleet_buy_s=med([int(r["blockTime"]) - c for r in b]),
                     fundings_pm10min=len(fund_near), funding_sol_pm10min=round(sum(float(r["amount"]) for r in fund_near), 2),
                     returns_30min_after_withdraw=len(ret_after), returns_sol_30min_after_withdraw=round(sum(float(r["amount"]) for r in ret_after), 2)))
with open(os.path.join(OUT, "gekko_pools.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w_ = csv.DictWriter(f, fieldnames=list(prow[0].keys()), delimiter=";")
    w_.writeheader()
    w_.writerows(prow)

res = dict(
    wallets=len(rows), trades=len(TR), gekko_pools=len(GPOOL),
    with_trades=sum(1 for r in rows if r["buys"] or r["sells"]),
    trade_result_total=round(sum(r["trade_result_sol"] for r in rows), 2), trade_result_median=med([r["trade_result_sol"] for r in rows]),
    losers=sum(1 for r in rows if r["trade_result_sol"] < 0), winners=sum(1 for r in rows if r["trade_result_sol"] > 0),
    buy_sol_total=round(sum(r["buy_sol"] for r in rows), 2), sell_sol_total=round(sum(r["sell_sol"] for r in rows), 2),
    funded_total=round(sum(r["funded_sol"] for r in rows), 2), returned_total=round(sum(r["returned_sol"] for r in rows), 2),
    gekko_buy_share=round(sum(r["gekko_pool_buys"] for r in rows) / max(1, sum(r["buys"] for r in rows)), 3),
    gekko_buy_sol_share=round(sum(r["gekko_pool_buy_sol"] for r in rows) / max(1e-9, sum(r["buy_sol"] for r in rows)), 3),
    pools_traded_median=med([r["pools_traded"] for r in rows]),
    fund_to_buy_s=dict(n=len(fund_to_buy), median=med(fund_to_buy), q10=sorted(fund_to_buy)[len(fund_to_buy) // 10] if fund_to_buy else "",
                       q90=sorted(fund_to_buy)[len(fund_to_buy) * 9 // 10] if fund_to_buy else "", within_60s=sum(1 for x in fund_to_buy if x <= 60)),
    sell_to_return_s=dict(n=len(sell_to_return), median=med(sell_to_return), within_60s=sum(1 for x in sell_to_return if x <= 60)),
    return_covered_by_sells=sum(1 for r, s in return_vs_sells if s >= r * 0.99), returns_n=len(return_vs_sells),
    return_to_sells_ratio_median=med([r / s for r, s in return_vs_sells if s > 0]),
    buy_pool_age_s=dict(n=len(buy_pool_age), median=med(buy_pool_age), within_60s=sum(1 for x in buy_pool_age if 0 <= x <= 60)),
    pools=prow,
)
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k != "pools"}, ensure_ascii=False, indent=1))
for p in prow:
    print({k: p[k] for k in ("pool", "create_utc", "first_withdraw_tx_after_min", "main_withdraw_after_min_sol_pools", "fleet_wallets_buying", "fleet_buy_sol", "fleet_sell_sol", "fleet_sell_sol_before_withdraw",
                             "first_fleet_buy_s", "median_fleet_buy_s", "fundings_pm10min", "funding_sol_pm10min", "returns_30min_after_withdraw", "returns_sol_30min_after_withdraw")})
