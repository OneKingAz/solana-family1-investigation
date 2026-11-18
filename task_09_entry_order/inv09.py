"""Task 09: exact entry order of the nine wallets into the coins all nine bought (task 7 legs). RPC (Helius, HELIUS_KEY of D:\\bot\\.env,
never printed): getBlock(signatures only) -> transaction index inside the block for every first buy; getSignaturesForAddress(pool,
before = first buy of the nine) -> pool activity before the nine; getTransaction of the oldest <=10 pool tx -> who created / bought first.
Caches: analysis/inv09_cache.json. Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_09\\"""
import collections, csv, datetime as dt, itertools, json, os, random, statistics, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
T7 = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_07"
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_09"
os.makedirs(OUT, exist_ok=True)
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
H = "https://mainnet.helius-rpc.com/?api-key=" + K
LK, LAST, CALLS = threading.Lock(), [0.0], [0]


def rpc(m, p):
    for k in range(6):
        with LK:
            g = 0.12 - (time.time() - LAST[0])
            if g > 0:
                time.sleep(g)
            LAST[0] = time.time()
            CALLS[0] += 1
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(H, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                                         headers={"Content-Type": "application/json"}), timeout=90).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
        time.sleep(1 + k)
    return None


NINE = [r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv")]
N = set(NINE)
SH = {w: w[:8] for w in NINE}
legs = [l for l in rd(os.path.join(T7, "nine_swap_legs.csv")) if l["signer"] in N and l["side"] == "BUY" and l["mint"]]
coins = [r for r in rd(os.path.join(T7, "nine_coin_net_positions.csv")) if r["wallets_bought"] == "9"]
COINS = {r["mint"]: r for r in coins}
CACHE = os.path.join(A, "inv09_cache.json")
C = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {"idx": {}, "pool": {}, "early": {}}
lockc = threading.Lock()


def save():
    with lockc:
        json.dump(C, open(CACHE, "w", encoding="utf-8"))


# first buy of each wallet in each coin (candidates: all buys in the wallet's earliest slot)
by = collections.defaultdict(list)
for l in legs:
    if l["mint"] in COINS:
        by[(l["mint"], l["signer"])].append(l)
first = {}
need_slots = set()
for k, ls in by.items():
    s0 = min(int(l["slot"]) for l in ls)
    cand = [l for l in ls if int(l["slot"]) == s0]
    first[k] = cand
    need_slots.add(s0)
# also every slot where two or more of the nine have their first buy (needed for order) — already included
todo = sorted(s for s in need_slots if str(s) not in C["idx"])
print(f"монет {len(COINS)}, первых покупок {len(first)}, слотов {len(need_slots)}, качаю блоков {len(todo)}", flush=True)


def get_block(s):
    b = rpc("getBlock", [s, {"transactionDetails": "signatures", "rewards": False, "maxSupportedTransactionVersion": 0, "commitment": "confirmed"}])
    if b and "signatures" in b:
        with lockc:
            C["idx"][str(s)] = {sig: i for i, sig in enumerate(b["signatures"]) if sig in want.get(s, ())}
            C["idx"][str(s) + "_n"] = len(b["signatures"])


want = collections.defaultdict(set)
for k, ls in first.items():
    for l in ls:
        want[int(l["slot"])].add(l["signature"])
with ThreadPoolExecutor(4) as ex:
    list(ex.map(get_block, todo))
save()

entry = {}
for (mt, w), ls in first.items():
    s = int(ls[0]["slot"])
    idx = C["idx"].get(str(s), {})
    best = min(ls, key=lambda l: idx.get(l["signature"], 10 ** 9))
    entry[(mt, w)] = dict(slot=s, tx_index=idx.get(best["signature"], ""), block_txs=C["idx"].get(str(s) + "_n", ""), signature=best["signature"],
                          blockTime=int(best["blockTime"]), pool=best["pool"], program=best["program"], wsol=float(best["wsol_to_pool"]))

# pool history before the nine's first buy
pools = {}
for mt in COINS:
    es = sorted((e for (m2, w), e in entry.items() if m2 == mt), key=lambda e: (e["slot"], e["tx_index"] if e["tx_index"] != "" else 10 ** 9))
    pools[mt] = (es[0]["pool"], es[0]["signature"], es[0]["slot"], es[0]["blockTime"])


def pool_hist(mt):
    pool, sig, slot, bt = pools[mt]
    if mt in C["pool"]:
        return
    out, before = [], sig
    for _ in range(5):  # up to 5000 earlier tx
        page = rpc("getSignaturesForAddress", [pool, {"before": before, "limit": 1000}]) or []
        out += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    ok = [x for x in out if not x.get("err")]
    complete = len(out) < 5000
    oldest = sorted(ok, key=lambda x: x["slot"])[:10]
    early = []
    for x in oldest:
        t = rpc("getTransaction", [x["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not t:
            continue
        logs = " ".join(t["meta"].get("logMessages") or [])
        payer = t["transaction"]["message"]["accountKeys"][0]["pubkey"]
        kind = "create" if "CreatePool" in logs or "InitializePool" in logs or "initialize" in logs.lower() and "pool" in logs.lower() else (
            "swap" if ("Instruction: Sell" in logs or "Instruction: Buy" in logs or "Swap" in logs) else "other")
        early.append(dict(signature=x["signature"], slot=x["slot"], blockTime=x.get("blockTime"), payer=payer, kind=kind))
    with lockc:
        C["pool"][mt] = dict(pool=pool, before_total=len(out), before_ok=len(ok), complete=complete,
                             oldest_slot=oldest[0]["slot"] if oldest else None, oldest_time=oldest[0].get("blockTime") if oldest else None)
        C["early"][mt] = early


with ThreadPoolExecutor(3) as ex:
    list(ex.map(pool_hist, [m for m in COINS if m not in C["pool"]]))
save()
print("запросов", CALLS[0], flush=True)


# ---------- analysis ----------
def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        wr.writeheader()
        wr.writerows(rows)


creators = {r["mint"]: r["creator"] for r in coins}
orders, rows, crows = {}, [], []
for mt in sorted(COINS, key=lambda m: pools[m][2]):
    es = sorted(((w, e) for (m2, w), e in entry.items() if m2 == mt), key=lambda we: (we[1]["slot"], we[1]["tx_index"] if we[1]["tx_index"] != "" else 10 ** 9))
    orders[mt] = [w for w, _ in es]
    t0, s0 = es[0][1]["blockTime"], es[0][1]["slot"]
    for rank, (w, e) in enumerate(es, 1):
        rows.append(dict(mint=mt, creator=creators.get(mt, ""), pool=e["pool"], program=e["program"], wallet=w, rank=rank, signature=e["signature"], slot=e["slot"],
                         tx_index=e["tx_index"], block_txs=e["block_txs"], time_utc=iso(e["blockTime"]), seconds_after_first=e["blockTime"] - t0,
                         slots_after_first=e["slot"] - s0, first_buy_wsol=e["wsol"]))
    ph = C["pool"].get(mt, {})
    early = C["early"].get(mt, [])
    cr = next((x for x in early if x["kind"] == "create"), None)
    first_swaps = [x for x in early if x["kind"] == "swap"][:5]
    crows.append(dict(mint=mt, creator=creators.get(mt, ""), pool=pools[mt][0], program=es[0][1]["program"], nine_first_utc=iso(t0), nine_first_slot=s0,
                      nine_last_entry_utc=iso(es[-1][1]["blockTime"]), nine_spread_s=es[-1][1]["blockTime"] - t0, nine_spread_slots=es[-1][1]["slot"] - s0,
                      nine_in_same_slot_max=max(collections.Counter(e["slot"] for _, e in es).values()),
                      order=" ".join(SH[w] for w in orders[mt]),
                      pool_tx_before_nine=ph.get("before_ok", ""), pool_history_complete=int(bool(ph.get("complete"))),
                      pool_created_utc=iso(cr["blockTime"]) if cr and cr.get("blockTime") else (iso(ph["oldest_time"]) + " (самая ранняя видимая)" if ph.get("oldest_time") else ""),
                      created_by=cr["payer"] if cr else "", seconds_create_to_nine=(t0 - cr["blockTime"]) if cr and cr.get("blockTime") else "",
                      first_swappers=" ".join(f"{x['payer'][:8]}{'*' if x['payer'] in N else ''}" for x in first_swaps)))
wcsv("entry_order.csv", rows)
wcsv("coin_entry_summary.csv", crows)

# rank statistics per wallet
M = list(orders.values())
rank_of = {mt: {w: i + 1 for i, w in enumerate(o)} for mt, o in orders.items()}
wr = []
for w in NINE:
    rs = [rank_of[mt][w] for mt in orders]
    c = collections.Counter(rs)
    wr.append(dict(wallet=w, coins=len(rs), mean_rank=round(statistics.mean(rs), 3), median_rank=statistics.median(rs), first=c[1], last=c[9],
                   **{f"rank_{i}": c[i] for i in range(1, 10)}))
wcsv("wallet_rank_stats.csv", wr)


def kendall_w(orders_list):
    n, m = 9, len(orders_list)
    R = collections.Counter()
    for o in orders_list:
        for i, w in enumerate(o):
            R[w] += i + 1
    mean = m * (n + 1) / 2
    S = sum((R[w] - mean) ** 2 for w in NINE)
    return 12 * S / (m * m * (n ** 3 - n))


W_obs = kendall_w(M)
random.seed(1)
perm = []
for _ in range(2000):
    perm.append(kendall_w([random.sample(NINE, 9) for _ in M]))
p_W = sum(1 for x in perm if x >= W_obs) / len(perm)
# identical orders / most common first
same_order = collections.Counter(tuple(o) for o in M).most_common(3)
pair_agree = []
for a, b in itertools.combinations(NINE, 2):
    ab = sum(1 for o in M if o.index(a) < o.index(b))
    pair_agree.append(max(ab, len(M) - ab) / len(M))

# rounds: in the full buy sequence of the nine on a coin, share of 9-windows with 9 distinct wallets
round_share, gaps = [], []
for mt in COINS:
    seq = sorted((l for l in legs if l["mint"] == mt), key=lambda l: (int(l["slot"]), l["signature"]))
    ws = [l["signer"] for l in seq]
    if len(ws) >= 9:
        win = [len(set(ws[i:i + 9])) == 9 for i in range(len(ws) - 8)]
        round_share.append(sum(win) / len(win))
    per = collections.defaultdict(list)
    for l in seq:
        per[l["signer"]].append(int(l["blockTime"]))
    for w, ts in per.items():
        gaps += [b - a for a, b in zip(ts, ts[1:])]
# expected share for random sequences of the same length (9 equally likely wallets)
exp_random = 362880 / 9 ** 9
sz = [float(r["first_buy_wsol"]) for r in rows]
res = dict(coins=len(COINS), first_buys=len(rows), tx_index_known=sum(1 for r in rows if r["tx_index"] != ""),
           spread_s_median=statistics.median([c["nine_spread_s"] for c in crows]), spread_s_min=min(c["nine_spread_s"] for c in crows),
           spread_s_max=max(c["nine_spread_s"] for c in crows), spread_slots_median=statistics.median([c["nine_spread_slots"] for c in crows]),
           same_slot_max_median=statistics.median([c["nine_in_same_slot_max"] for c in crows]),
           kendall_W=round(W_obs, 4), kendall_W_random_mean=round(statistics.mean(perm), 4), kendall_W_random_p95=round(sorted(perm)[int(len(perm) * .95)], 4), p_value=p_W,
           identical_orders_top=[(" ".join(SH[w] for w in o), n) for o, n in same_order],
           first_wallet=dict(collections.Counter(SH[o[0]] for o in M).most_common()), last_wallet=dict(collections.Counter(SH[o[-1]] for o in M).most_common()),
           pair_order_agreement_median=round(statistics.median(pair_agree), 3), pair_order_agreement_max=round(max(pair_agree), 3),
           rounds_share_median=round(statistics.median(round_share), 4) if round_share else None, rounds_share_random=round(exp_random, 6),
           buy_gap_same_wallet_median_s=statistics.median(gaps) if gaps else None,
           create_to_nine_s=sorted(c["seconds_create_to_nine"] for c in crows if c["seconds_create_to_nine"] != ""),
           pool_tx_before_nine_median=statistics.median([c["pool_tx_before_nine"] for c in crows if c["pool_tx_before_nine"] != ""]) if crows else None,
           first_buy_wsol_median=round(statistics.median(sz), 4), calls=CALLS[0])
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
for w in wr:
    print(w)
