"""Task 12: control group. Every participant (fee payer) of a sample of pools, decoded with the same leg logic as task 7, compared by group:
nine / other fleet-109 wallets / creators / others (dust buyers < 0.01 SOL separately). Sample: pool ErVpTsjX (all tx already in inv05_raw)
+ 6 pools drawn at random (seed 12) from the 58 coins all nine traded, restricted to sessions of 50-400 nine-tx (fetch size). For each sampled
pool all tx from pool creation to the nine's last trade in it (getSignaturesForAddress + getTransaction; Helius, HELIUS_KEY of D:\\bot\\.env,
never printed; raw cache analysis/inv12_raw.jsonl.gz). Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_12\\"""
import collections, csv, datetime as dt, gzip, json, os, random, statistics, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, "investigation_task_12")
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
WSOL = "So11111111111111111111111111111111111111112"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
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


def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b


NINE = [r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))]
N = set(NINE)
FLEET = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_03\park_wallet_flows.csv"))} - N
SESS = {r["mint"]: r for r in rd(os.path.join(D, r"investigation_task_11\coin_sessions.csv"))}
CRE = {r["creator"] for r in SESS.values() if r["creator"]} | {"Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL", "CPC8iEE1PripNpd7VjofSHENYnoKpFnjmZFDtE8m7QT2", "89coAVTUZetQ4K6Ct4nsqtLtMCaR4X2mWStdBsmdECur"}
legs9 = [l for l in rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv")) if l["signer"] in N and l["mint"]]
all9 = {r["mint"] for r in rd(os.path.join(D, r"investigation_task_07\nine_coin_net_positions.csv")) if r["wallets_bought"] == "9"}
pool_of, last_sig, last_slot = {}, {}, {}
for l in legs9:
    pool_of[l["mint"]] = l["pool"]
    if l["mint"] not in last_slot or int(l["slot"]) > last_slot[l["mint"]]:
        last_slot[l["mint"]], last_sig[l["mint"]] = int(l["slot"]), l["signature"]
ERVP_MINT = "EV5nTWTsmpq6HuLCzpqVSyqSSwMPLFX9cU59WTou5wvD"
cand = sorted(m for m in all9 if m != ERVP_MINT and 50 <= int(SESS[m]["txs"]) <= 400)
random.seed(12)
ORDER = random.sample(cand, len(cand))  # random order; pools taken in this order, skipping pools with > 5000 tx, until 6 pools or 20000 tx
SAMPLE = []
print("кандидатов", len(cand), flush=True)
RAW = os.path.join(A, "inv12_raw.jsonl.gz")
have = {}
if os.path.exists(RAW):
    with gzip.open(RAW, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            have[d["signature"]] = d
lockw = threading.Lock()
pool_sigs, skipped, total = {}, [], 0
for m in ORDER:
    if len(SAMPLE) >= 6 or total >= 20000:
        break
    out, before = [], last_sig[m]
    while len(out) <= 5000:
        page = rpc("getSignaturesForAddress", [pool_of[m], {"before": before, "limit": 1000}]) or []
        out += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    n = len(out) + 1
    if n > 5000:
        skipped.append((m, ">5000"))
        print(m[:8], "пропущен: больше 5000 транзакций", flush=True)
        continue
    pool_sigs[m] = [x["signature"] for x in out if not x.get("err")] + [last_sig[m]]
    SAMPLE.append(m)
    total += len(pool_sigs[m])
    print(m[:8], "транзакций пула до конца торговли девяти:", len(pool_sigs[m]), flush=True)
print("выбрано", SAMPLE, "пропущено", skipped, flush=True)


def fetch(args):
    sig, mt = args
    if sig in have:
        return
    t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if t:
        with lockw:
            with gzip.open(RAW, "at", encoding="utf-8") as f:
                f.write(json.dumps({"signature": sig, "mint": mt, "tx": t}) + "\n")
            have[sig] = {"signature": sig, "mint": mt, "tx": t}


with ThreadPoolExecutor(6) as ex:
    list(ex.map(fetch, [(s, m) for m in SAMPLE for s in pool_sigs[m]]))
print("скачано", len(have), "запросов", CALLS[0], flush=True)
# ErVp from inv05 raw
txs = [(d["mint"], d["tx"], d["signature"]) for d in have.values()]
with gzip.open(os.path.join(A, "inv05_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        txs.append((ERVP_MINT, d["tx"], d["signature"]))
POOLS = [ERVP_MINT] + SAMPLE


def decode(t):
    """legs of the fee payer: list of (side, wsol_in, wsol_out, coin_in_raw, coin_out_raw, minout_arg, coin_in_arg, program)"""
    m = t["meta"]
    if m.get("err"):
        return None, []
    msg = t["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    signer = keys[0]
    tb = {}
    for b in (m.get("preTokenBalances") or []) + (m.get("postTokenBalances") or []):
        tb[keys[b["accountIndex"]]] = (b["mint"], b.get("owner"))
    inner = {g["index"]: g["instructions"] for g in m.get("innerInstructions") or []}
    for g in inner.values():
        for ins in g:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type", "").startswith("initializeAccount"):
                tb.setdefault(p["info"]["account"], (p["info"]["mint"], p["info"].get("owner")))
    out = []
    for i, ins in enumerate(msg["instructions"]):
        pid = ins.get("programId")
        if pid not in (AMM, MET) or "data" not in ins:
            continue
        raw = b58dec(ins["data"])
        if raw[:8].hex() == "ea66c2cb96483ee5":
            continue
        accs = ins.get("accounts", [])
        owner_pool = accs[0]
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
            auth = inf.get("authority")
            if auth == signer and dp:
                fl[("in", mint == WSOL)] += amt
            elif sp and tb.get(dst, (None, None))[1] == signer:
                fl[("out", mint == WSOL)] += amt
            elif auth == signer and not dp:
                fl[("fee", mint == WSOL)] += amt
        wi, wo, ci, co = fl[("in", True)], fl[("out", True)], fl[("in", False)], fl[("out", False)]
        side = "BUY" if wi and co else "SELL" if ci and wo else "?"
        vals = [int.from_bytes(raw[8 + 8 * k:16 + 8 * k], "little") for k in range((len(raw) - 8) // 8)]
        out.append(dict(side=side, wsol_in=wi / 1e9, wsol_out=wo / 1e9, coin_in=ci + fl[("fee", False)], coin_out=co, args=vals[:2], program="PumpSwap" if pid == AMM else "Meteora"))
    return signer, out


per = collections.defaultdict(lambda: dict(txs=0, buy=0, sell=0, rt=0, buys_sol=[], kept=[], minout_eq=0, rt_pumpswap=0, first=dict(), pools=set()))
created = {}
for mt, t, sig in txs:
    signer, lg = decode(t)
    if not signer:
        continue
    logs = " ".join(t["meta"].get("logMessages") or [])
    if "CreatePool" in logs or ("initialize" in logs.lower() and "pool" in logs.lower()):
        created[mt] = min(created.get(mt, 10 ** 12), t["blockTime"])
    if not lg:
        continue
    s = per[signer]
    s["txs"] += 1
    s["pools"].add(mt)
    sides = [l["side"] for l in lg]
    s["buy"] += sides.count("BUY")
    s["sell"] += sides.count("SELL")
    for l in lg:
        if l["side"] == "BUY":
            s["buys_sol"].append(l["wsol_in"])
            s["first"][mt] = min(s["first"].get(mt, 10 ** 12), t["blockTime"])
    if sides[:2] == ["BUY", "SELL"]:
        s["rt"] += 1
        b, se = lg[0], lg[1]
        if b["coin_out"]:
            s["kept"].append(100 * (b["coin_out"] - se["coin_in"]) / b["coin_out"])
        if b["program"] == "PumpSwap":
            s["rt_pumpswap"] += 1
            if len(b["args"]) > 1 and len(se["args"]) > 0 and b["args"][1] == se["args"][0]:
                s["minout_eq"] += 1


def group(w, s):
    if w in N:
        return "девять"
    if w in FLEET:
        return "парк-100"
    if w in CRE:
        return "создатели"
    if s["buys_sol"] and statistics.median(s["buys_sol"]) < 0.01:
        return "пыль (покупка < 0.01 SOL)"
    return "прочие"


rows = []
for w, s in per.items():
    g = group(w, s)
    ent = [s["first"][m] - created[m] for m in s["first"] if m in created]
    rows.append(dict(wallet=w, group=g, pools=len(s["pools"]), txs=s["txs"], buy_legs=s["buy"], sell_legs=s["sell"], roundtrip_txs=s["rt"],
                     roundtrip_share=round(s["rt"] / s["txs"], 4) if s["txs"] else 0, buy_sol_median=round(statistics.median(s["buys_sol"]), 6) if s["buys_sol"] else "",
                     kept_pct_median=round(statistics.median(s["kept"]), 4) if s["kept"] else "", minout_equals_sell_share=round(s["minout_eq"] / s["rt_pumpswap"], 4) if s["rt_pumpswap"] else "",
                     entry_after_create_s_median=statistics.median(ent) if ent else ""))
rows.sort(key=lambda r: (r["group"], -r["txs"]))
with open(os.path.join(OUT, "control_wallets.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(rows)
G = []
for g in ("девять", "парк-100", "создатели", "прочие", "пыль (покупка < 0.01 SOL)"):
    R = [r for r in rows if r["group"] == g]
    if not R:
        continue
    tx = sum(r["txs"] for r in R)
    rt = sum(r["roundtrip_txs"] for r in R)
    bs = [b for w, s in per.items() if group(w, s) == g for b in s["buys_sol"]]
    kp = [k for w, s in per.items() if group(w, s) == g for k in s["kept"]]
    me = sum(s["minout_eq"] for w, s in per.items() if group(w, s) == g)
    rp = sum(s["rt_pumpswap"] for w, s in per.items() if group(w, s) == g)
    ent = [r["entry_after_create_s_median"] for r in R if r["entry_after_create_s_median"] != ""]
    G.append(dict(group=g, wallets=len(R), wallets_in_2plus_pools=sum(1 for r in R if r["pools"] >= 2), txs=tx, buy_legs=sum(r["buy_legs"] for r in R),
                  sell_legs=sum(r["sell_legs"] for r in R), roundtrip_txs=rt, roundtrip_share=round(rt / tx, 4) if tx else 0,
                  wallets_with_any_roundtrip=sum(1 for r in R if r["roundtrip_txs"] > 0), buy_sol_median=round(statistics.median(bs), 6) if bs else "",
                  buy_sol_p90=round(sorted(bs)[int(.9 * len(bs))], 6) if bs else "", kept_pct_median=round(statistics.median(kp), 4) if kp else "",
                  minout_equals_sell=f"{me}/{rp}", entry_after_create_s_median=statistics.median(ent) if ent else ""))
with open(os.path.join(OUT, "control_groups.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(G[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(G)
# other round-trippers outside the nine (same tx buy->sell with minout == sell): who are they
rt_others = sorted([r for r in rows if r["group"] != "девять" and r["roundtrip_txs"] >= 5], key=lambda r: -r["roundtrip_txs"])[:30]
res = dict(pools=POOLS, skipped_pools=skipped, pool_tx={m: len(v) for m, v in pool_sigs.items()}, created_found=len(created), txs_decoded=sum(r["txs"] for r in rows), groups=G, top_other_roundtrippers=rt_others, calls=CALLS[0])
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for g in G:
    print(g)
for r in rt_others[:15]:
    print("RT", r)
