"""Task 13 (user: what do the bots do when an outside wallet buys their coin?). No RPC. Pools with COMPLETE history only:
ErVpTsjX (inv05_raw, all tx) and the 6 random pools of inv12 (all tx from creation to the nine's last trade). Large pools sampled evenly (inv12L)
are NOT used — gaps would fake "no reaction".
Groups of signers: nine / fleet-100 / pool creators / dust (median buy < 0.01 SOL) / outsiders (everyone else).
Event = an outsider BUY (pure buy, no sell in the same tx) of >= 0.05 SOL. For windows 5/15/30/60 s after the event:
nine tx count, nine net SOL into the pool, fleet tx count, creator tx count, creator withdraw, largest single sell (SOL out of the pool) by anyone,
pool SOL change. Baseline: every 5th second of the same pool's life with no outsider buy in the previous 60 s, same metrics.
Also: every Withdraw — was there an outsider buy in the 30 s before it, versus the share of pool time covered by such 30 s windows.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_13\\"""
import bisect, collections, csv, datetime as dt, gzip, json, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, "investigation_task_13")
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
WSOL = "So11111111111111111111111111111111111111112"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
NINE = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))}
FLEET = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_03\park_wallet_flows.csv"))} - NINE
PF = rd(os.path.join(D, r"investigation_task_11\v2\pool_creator_fields.csv"))
CRE = {r["pool_init_payer"] for r in PF if r["pool_init_payer"]} | {r["pool_field_creator"] for r in PF if r["pool_field_creator"]}
ERVP = "EV5nTWTsmpq6HuLCzpqVSyqSSwMPLFX9cU59WTou5wvD"
# known Family-1 wallets that are NOT in the nine / 100: the 170-wallet fleet, dust markers, small repeaters, creators (roles of the 40-pool data,
# analyst_data_2026-11-18/sol_buyers.csv) + treasury, sponsor, GH74zHdN. Without this the sponsor 3azG8rmt was counted as an "outsider".
FAMILY = {r["who"] for r in rd(os.path.join(D, r"analyst_data_2026-11-18\sol_buyers.csv")) if r["role"] and r["role"] != "посторонний"} | {
    "B7StC42h126Hmtkw4GoRMcaHA5ZuKawfa9fCSTV6UMSj", "3azG8rmtPnNUz77a6UqBKt1ykpk3JQpLLNTaoXW31b34", "GH74zHdNZWcF9zRzw3KoNG8GNgUvtzokNwkSFMeWTvi6"}
# completeness: pools listed by inv12 with their tx count
n12 = json.load(open(os.path.join(D, r"investigation_task_12\_numbers.json"), encoding="utf-8")) if os.path.exists(os.path.join(D, r"investigation_task_12\_numbers.json")) else {}
listed = dict(n12.get("pool_tx", {}))
if not listed:  # inv12 not finished: parse its log
    for line in open(os.path.join(A, "inv12.out"), encoding="utf-8", errors="ignore"):
        if "транзакций пула до конца торговли девяти" in line:
            pass
L = json.load(open(os.path.join(A, "inv12L_pools.json"), encoding="utf-8")) if os.path.exists(os.path.join(A, "inv12L_pools.json")) else {}


def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b


by_pool = collections.defaultdict(dict)
with gzip.open(os.path.join(A, "inv12_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d["mint"] in L:
            continue
        by_pool[d["mint"]][d["signature"]] = d["tx"]
with gzip.open(os.path.join(A, "inv05_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        by_pool[ERVP][d["signature"]] = d["tx"]
complete = {}
for m, txs in by_pool.items():
    want = 10297 if m == ERVP else listed.get(m)
    complete[m] = (len(txs), want)
POOLS = [m for m, (have, want) in complete.items() if want and have >= 0.97 * want]
print("пулы:", {m[:8]: complete[m] for m in complete}, "полные:", [m[:8] for m in POOLS], flush=True)


def decode(t, pool_owner_hint=None):
    m = t["meta"]
    msg = t["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    signer = keys[0]
    logs = " ".join(m.get("logMessages") or [])
    tb = {}
    for b in (m.get("preTokenBalances") or []) + (m.get("postTokenBalances") or []):
        tb[keys[b["accountIndex"]]] = (b["mint"], b.get("owner"))
    inner = {g["index"]: g["instructions"] for g in m.get("innerInstructions") or []}
    for g in inner.values():
        for ins in g:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type", "").startswith("initializeAccount"):
                tb.setdefault(p["info"]["account"], (p["info"]["mint"], p["info"].get("owner")))
    legs, pool = [], None
    for i, ins in enumerate(msg["instructions"]):
        pid = ins.get("programId")
        if pid not in (AMM, MET) or "data" not in ins:
            continue
        raw = b58dec(ins["data"])
        if raw[:8].hex() == "ea66c2cb96483ee5":
            continue
        owner_pool = ins.get("accounts", [""])[0]
        pool = pool or owner_pool
        fl = collections.Counter()
        for x in inner.get(i, []):
            p = x.get("parsed") if isinstance(x, dict) else None
            if not (isinstance(p, dict) and p.get("type") in ("transfer", "transferChecked") and x.get("program") in ("spl-token", "spl-token-2022")):
                continue
            inf = p["info"]
            src, dst = inf["source"], inf["destination"]
            amt = int(inf["tokenAmount"]["amount"]) if "tokenAmount" in inf else int(inf["amount"])
            mint = inf.get("mint") or (tb.get(src) or tb.get(dst) or ("?",))[0]
            sp, dp = tb.get(src, (None, None))[1] == owner_pool, tb.get(dst, (None, None))[1] == owner_pool
            if inf.get("authority") == signer and dp:
                fl[("in", mint == WSOL)] += amt
            elif sp and tb.get(dst, (None, None))[1] == signer:
                fl[("out", mint == WSOL)] += amt
        wi, co, ci, wo = fl[("in", True)], fl[("out", False)], fl[("in", False)], fl[("out", True)]
        legs.append(("BUY" if wi and co else "SELL" if ci and wo else "?", wi / 1e9, wo / 1e9))
    # pool SOL after the tx: largest WSOL account owned by a non-user after the tx
    post_w = None
    for b in m.get("postTokenBalances") or []:
        if b["mint"] == WSOL and b.get("owner") not in (signer,):
            v = int(b["uiTokenAmount"]["amount"]) / 1e9
            post_w = v if post_w is None or v > post_w else post_w
    return signer, legs, "Instruction: Withdraw" in logs, post_w


events, base_rows, wd_rows, BINS = [], [], [], []
WIN = (5, 15, 30, 60)
for m in POOLS:
    seq = []
    for sig, t in by_pool[m].items():
        if (t.get("meta") or {}).get("err"):
            continue
        signer, legs, wd, post_w = decode(t)
        seq.append((t["slot"], t["blockTime"], sig, signer, legs, wd, post_w))
    seq.sort(key=lambda x: (x[0], x[2]))
    # buy sizes per signer (dust detection)
    bs = collections.defaultdict(list)
    for x in seq:
        for side, wi, wo in x[4]:
            if side == "BUY":
                bs[x[3]].append(wi)

    def grp(w):
        if w in NINE:
            return "nine"
        if w in FLEET:
            return "fleet"
        if w in CRE:
            return "creator"
        if w in FAMILY:
            return "family_other"
        if bs.get(w) and statistics.median(bs[w]) < 0.01:
            return "dust"
        return "outsider"

    T = [x[1] for x in seq]
    G = [grp(x[3]) for x in seq]
    W = []
    last = None
    for x in seq:
        last = x[6] if x[6] is not None else last
        W.append(last)

    def window(i0, t0, w):
        j = bisect.bisect_right(T, t0 + w)
        sl = range(i0 + 1, j)
        nine_n = sum(1 for k in sl if G[k] == "nine")
        nine_net = sum(wi - wo for k in sl if G[k] == "nine" for s, wi, wo in seq[k][4])
        fleet_n = sum(1 for k in sl if G[k] == "fleet")
        cr_n = sum(1 for k in sl if G[k] == "creator")
        wd = int(any(seq[k][5] for k in sl))
        big_sell = max([wo for k in sl for s, wi, wo in seq[k][4] if s == "SELL"] or [0])
        dw = (W[j - 1] - W[i0]) if j - 1 >= i0 and W[j - 1] is not None and W[i0] is not None else None
        return dict(nine_tx=nine_n, nine_net_sol=round(nine_net, 6), fleet_tx=fleet_n, creator_tx=cr_n, withdraw=wd, largest_sell_sol=round(big_sell, 6),
                    pool_sol_change=round(dw, 6) if dw is not None else "")

    ev_idx = [i for i, x in enumerate(seq) if G[i] == "outsider" and x[4] and all(s == "BUY" for s, _, _ in x[4]) and sum(wi for _, wi, _ in x[4]) >= 0.05]
    ev_t = [T[i] for i in ev_idx]
    # activity-controlled test: 15 s bins over the pool's life; does the NEXT bin's nine/fleet activity change more after a bin with an
    # outsider buy than after a bin without one, at the same current activity level?
    t0b = T[0]
    nb = (T[-1] - t0b) // 15 + 1
    nine_b, fleet_b, out_b, cre_b = [0] * nb, [0] * nb, [0] * nb, [0] * nb
    for i, x in enumerate(seq):
        b = (T[i] - t0b) // 15
        if G[i] == "nine":
            nine_b[b] += 1
        elif G[i] == "fleet":
            fleet_b[b] += 1
        elif G[i] == "creator":
            cre_b[b] += 1
    for i in ev_idx:
        out_b[(T[i] - t0b) // 15] += 1
    for b in range(nb - 1):
        BINS.append(dict(mint=m, bin=b, age_s=b * 15, outsider_buys=out_b[b], nine_now=nine_b[b], nine_next=nine_b[b + 1], fleet_now=fleet_b[b], fleet_next=fleet_b[b + 1],
                         creator_next=cre_b[b + 1]))
    for i in ev_idx:
        row = dict(mint=m, signature=seq[i][2], time_utc=iso(T[i]), buyer=seq[i][3], buy_sol=round(sum(wi for _, wi, _ in seq[i][4]), 6),
                   pool_sol_before=round(W[i - 1], 4) if i and W[i - 1] else "", seconds_since_pool_start=T[i] - T[0])
        for w in WIN:
            for k, v in window(i, T[i], w).items():
                row[f"{k}_{w}s"] = v
        events.append(row)
    # baseline: every 5 s, no outsider buy in the previous 60 s
    t = T[0]
    while t <= T[-1]:
        k = bisect.bisect_left(ev_t, t - 60)
        if not (k < len(ev_t) and ev_t[k] <= t):
            i0 = max(0, bisect.bisect_right(T, t) - 1)
            row = dict(mint=m, time_utc=iso(t))
            for w in WIN:
                for kk, v in window(i0, t, w).items():
                    row[f"{kk}_{w}s"] = v
            base_rows.append(row)
        t += 5
    # withdraws
    life = T[-1] - T[0]
    cover = 0
    prev_end = None
    for et in ev_t:
        s0, e0 = et, et + 30
        if prev_end is not None and s0 < prev_end:
            s0 = prev_end
        cover += max(0, e0 - s0)
        prev_end = max(prev_end or 0, e0)
    for i, x in enumerate(seq):
        if x[5]:
            k = bisect.bisect_left(ev_t, T[i] - 30)
            pre = [ev_t[j] for j in range(k, len(ev_t)) if ev_t[j] <= T[i]]
            wd_rows.append(dict(mint=m, signature=x[2], time_utc=iso(T[i]), by=x[3], by_group=G[i], seconds_since_pool_start=T[i] - T[0],
                                outsider_buy_within_30s_before=int(bool(pre)), seconds_after_last_outsider_buy=(T[i] - pre[-1]) if pre else "",
                                share_of_pool_life_covered_by_30s_after_outsider_buys=round(cover / life, 4) if life else ""))


def wcsv(name, rows):
    if rows:
        with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
            w.writeheader()
            w.writerows(rows)


wcsv("outsider_buys.csv", events)
wcsv("baseline_windows.csv", base_rows)
wcsv("withdrawals.csv", wd_rows)
comp = []
for w in WIN:
    for k in ("nine_tx", "nine_net_sol", "fleet_tx", "creator_tx", "withdraw", "largest_sell_sol", "pool_sol_change"):
        a = [r[f"{k}_{w}s"] for r in events if r[f"{k}_{w}s"] != ""]
        b = [r[f"{k}_{w}s"] for r in base_rows if r[f"{k}_{w}s"] != ""]
        comp.append(dict(window_s=w, metric=k, after_outsider_buy_mean=round(statistics.mean(a), 5) if a else "", n_events=len(a),
                         baseline_mean=round(statistics.mean(b), 5) if b else "", n_baseline=len(b),
                         ratio=round(statistics.mean(a) / statistics.mean(b), 3) if a and b and statistics.mean(b) else ""))
wcsv("comparison.csv", comp)
# by buy size
size = []
for lo, hi in ((0.05, 0.5), (0.5, 2), (2, 1e9)):
    R = [r for r in events if lo <= r["buy_sol"] < hi]
    if R:
        size.append(dict(buy_sol=f"{lo}–{hi if hi < 1e9 else '∞'}", events=len(R), withdraw_30s=sum(r["withdraw_30s"] for r in R),
                         nine_tx_30s_mean=round(statistics.mean(r["nine_tx_30s"] for r in R), 3), creator_tx_30s_mean=round(statistics.mean(r["creator_tx_30s"] for r in R), 3),
                         largest_sell_30s_mean=round(statistics.mean(r["largest_sell_sol_30s"] for r in R), 4)))
wcsv("by_buy_size.csv", size)
wcsv("bins_15s.csv", BINS)
# matched comparison: bins with the same current nine activity (nine_now) and the same pool, with vs without outsider buys
match = []
strata = collections.defaultdict(lambda: {"with": [], "without": []})
for r in BINS:
    if r["nine_now"] == 0 and r["fleet_now"] == 0:
        continue  # dead time (before the nine / after the session)
    key = (r["mint"], min(r["nine_now"], 8))
    strata[key]["with" if r["outsider_buys"] else "without"].append(r)
dn_w, dn_wo, df_w, df_wo, cr_w, cr_wo, ns = [], [], [], [], [], [], 0
for key, s in strata.items():
    if s["with"] and s["without"]:
        ns += 1
        mw = statistics.mean(x["nine_next"] - x["nine_now"] for x in s["with"])
        mo = statistics.mean(x["nine_next"] - x["nine_now"] for x in s["without"])
        dn_w.append(mw)
        dn_wo.append(mo)
        df_w.append(statistics.mean(x["fleet_next"] - x["fleet_now"] for x in s["with"]))
        df_wo.append(statistics.mean(x["fleet_next"] - x["fleet_now"] for x in s["without"]))
        cr_w.append(statistics.mean(x["creator_next"] for x in s["with"]))
        cr_wo.append(statistics.mean(x["creator_next"] for x in s["without"]))
diff = [a - b for a, b in zip(dn_w, dn_wo)]
matched = dict(strata_used=ns, bins_with_outsider=sum(len(s["with"]) for s in strata.values() if s["with"] and s["without"]),
               bins_without=sum(len(s["without"]) for s in strata.values() if s["with"] and s["without"]),
               nine_change_next_bin_with=round(statistics.mean(dn_w), 3) if dn_w else "", nine_change_next_bin_without=round(statistics.mean(dn_wo), 3) if dn_wo else "",
               strata_where_with_gt_without=sum(1 for d in diff if d > 0), strata_where_with_lt_without=sum(1 for d in diff if d < 0),
               fleet_change_with=round(statistics.mean(df_w), 3) if df_w else "", fleet_change_without=round(statistics.mean(df_wo), 3) if df_wo else "",
               creator_next_with=round(statistics.mean(cr_w), 4) if cr_w else "", creator_next_without=round(statistics.mean(cr_wo), 4) if cr_wo else "")
print("СОПОСТАВЛЕНИЕ ПРИ ОДИНАКОВОЙ АКТИВНОСТИ:", matched)
res = dict(pools=[m for m in POOLS], completeness={m: complete[m] for m in complete}, outsider_buys=len(events), baseline_points=len(base_rows),
           withdrawals=wd_rows, comparison=comp, by_size=size, matched=matched)
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for c in comp:
    if c["window_s"] in (15, 60):
        print(c)
for s in size:
    print(s)
for w in wd_rows:
    print("ВЫВОД", w)
