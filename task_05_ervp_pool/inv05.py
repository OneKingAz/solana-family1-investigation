"""Task 05 (18.11, user authorised RPC): trades of the 109 fleet wallets in the GEKKO creator's pool ErVpTsjX (17.11 13:42-14:47 UTC),
to explain the returns of 14:03-14:13 that came right after its liquidity withdrawal. Helius (HELIUS_KEY of D:\\bot\\.env, never printed).
Every transaction of the pool: signer, SOL into/out of the pool's WSOL vault (buy > 0 / sell < 0), the signer's own SOL change,
coin change of the signer, Withdraw / CreatePool. Raw transactions kept in analysis/inv05_raw.jsonl.gz (resumable).
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_05\\ ervp_trades.csv, ervp_wallets.csv (+ _numbers.json)."""
import collections, csv, datetime as dt, gzip, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_05"
os.makedirs(OUT, exist_ok=True)
POOL = "ErVpTsjXLTPu2LN5NGJc45BBGwGL937KZEaw5reda4PP"
GC = "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
WSOL = "So11111111111111111111111111111111111111112"
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
H = "https://mainnet.helius-rpc.com/?api-key=" + K
LK, LAST, CALLS = threading.Lock(), [0.0], [0]
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
                                                                         headers={"Content-Type": "application/json"}), timeout=60).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
        time.sleep(1 + k)
    return None


W109 = {r["wallet"] for r in csv.DictReader(open(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_03\park_wallet_flows.csv", encoding="utf-8-sig"), delimiter=";")}
sigs, before = [], None
while True:
    p = {"limit": 1000}
    if before:
        p["before"] = before
    page = rpc("getSignaturesForAddress", [POOL, p]) or []
    sigs += page
    if len(page) < 1000:
        break
    before = page[-1]["signature"]
sigs = [s for s in sigs if not s.get("err")]
RAW = os.path.join(A, "inv05_raw.jsonl.gz")
have = {}
if os.path.exists(RAW):
    with gzip.open(RAW, "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            have[d["signature"]] = d["tx"]
todo = [s["signature"] for s in sigs if s["signature"] not in have]
print(f"транзакций пула без ошибок: {len(sigs)}, уже скачано {len(have)}, качаю {len(todo)}", flush=True)
lockw = threading.Lock()


def fetch(sig):
    t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if t:
        with lockw:
            with gzip.open(RAW, "at", encoding="utf-8") as f:
                f.write(json.dumps({"signature": sig, "tx": t}) + "\n")
            have[sig] = t
    return sig


with ThreadPoolExecutor(6) as ex:
    for i, _ in enumerate(ex.map(fetch, todo), 1):
        if i % 500 == 0:
            print(f"  {i}/{len(todo)}, запросов {CALLS[0]}", flush=True)

# ---- parse ----
mint = None
rows = []
for sig, t in have.items():
    m = t.get("meta") or {}
    if m.get("err"):
        continue
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
    signer = keys[0]
    logs = " ".join(m.get("logMessages") or [])
    pre = {(b.get("owner"), b["mint"]): float(b["uiTokenAmount"]["uiAmount"] or 0) for b in m.get("preTokenBalances") or []}
    post = {(b.get("owner"), b["mint"]): float(b["uiTokenAmount"]["uiAmount"] or 0) for b in m.get("postTokenBalances") or []}
    if mint is None:
        for (o, mt) in post:
            if o == POOL and mt != WSOL:
                mint = mt
    d_pool_sol = post.get((POOL, WSOL), 0) - pre.get((POOL, WSOL), 0)
    d_signer_coin = post.get((signer, mint), 0) - pre.get((signer, mint), 0) if mint else 0
    i = keys.index(signer)
    d_signer_sol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
    kind = "withdraw" if "Instruction: Withdraw" in logs else "create" if "CreatePool" in logs else ("buy" if d_pool_sol > 0 else "sell" if d_pool_sol < 0 else "other")
    rows.append(dict(signature=sig, slot=t["slot"], unix=t["blockTime"], time_utc=iso(t["blockTime"]), signer=signer,
                     role="создатель GEKKO" if signer == GC else ("парк-109" if signer in W109 else ""), kind=kind,
                     pool_sol_change=round(d_pool_sol, 9), signer_sol_change=round(d_signer_sol, 9), signer_coin_change=round(d_signer_coin, 6),
                     pool_sol_after=round(post.get((POOL, WSOL), 0), 6)))
rows.sort(key=lambda r: (r["slot"], r["signature"]))
with open(os.path.join(OUT, "ervp_trades.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(rows)

# ---- per wallet (109) vs funding / withdraw / return ----
T = [r for r in csv.DictReader(open(os.path.join(A, "sol_export_transfers.csv"), encoding="utf-8-sig"), delimiter=";") if r["asset"] == "SOL" and r["in_trade"] != "True"]
fund = collections.defaultdict(list)
ret = collections.defaultdict(list)
for r in T:
    if r["source"] == GC and r["destination"] in W109:
        fund[r["destination"]].append((int(r["blockTime"]), float(r["amount"])))
    if r["destination"] == GC and r["source"] in W109:
        ret[r["source"]].append((int(r["blockTime"]), float(r["amount"])))
wd = [r for r in rows if r["kind"] == "withdraw" and r["signer"] == GC]
wd_t = wd[0]["unix"] if wd else None
cr = next((r for r in rows if r["kind"] == "create"), None)
wrows = []
for wlt in sorted(W109):
    tr = [r for r in rows if r["signer"] == wlt and r["kind"] in ("buy", "sell")]
    b = [r for r in tr if r["kind"] == "buy"]
    s = [r for r in tr if r["kind"] == "sell"]
    first_ret = min((t for t, _ in ret[wlt]), default=None)
    sells_before_ret = [r for r in s if first_ret and r["unix"] <= first_ret]
    sold_after_wd = [r for r in s if wd_t and r["unix"] >= wd_t]
    wrows.append(dict(wallet=wlt, buys=len(b), buy_sol=round(sum(r["pool_sol_change"] for r in b), 6), sells=len(s),
                      sell_sol=round(-sum(r["pool_sol_change"] for r in s), 6), trade_result_sol=round(-sum(r["pool_sol_change"] for r in tr), 6),
                      first_trade_utc=tr[0]["time_utc"] if tr else "", last_trade_utc=tr[-1]["time_utc"] if tr else "",
                      funded_before_first_return=round(sum(a for t, a in fund[wlt] if not first_ret or t < first_ret), 6),
                      first_return_utc=iso(first_ret) if first_ret else "", returned_sol=round(sum(a for _, a in ret[wlt]), 6),
                      sells_before_first_return_sol=round(-sum(r["pool_sol_change"] for r in sells_before_ret), 6),
                      sells_after_withdraw=len(sold_after_wd), last_sell_to_return_s=(first_ret - max(r["unix"] for r in sells_before_ret)) if sells_before_ret and first_ret else ""))
with open(os.path.join(OUT, "ervp_wallets.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(wrows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(wrows)

kinds = collections.Counter(r["kind"] for r in rows)
fleet = [r for r in rows if r["role"] == "парк-109" and r["kind"] in ("buy", "sell")]
others = [r for r in rows if r["role"] == "" and r["kind"] in ("buy", "sell")]
res = dict(calls=CALLS[0], txs=len(rows), kinds=dict(kinds), mint=mint, create=cr and dict(t=cr["time_utc"], slot=cr["slot"], sig=cr["signature"]),
           withdraws=[dict(t=r["time_utc"], slot=r["slot"], sig=r["signature"], pool_sol_change=r["pool_sol_change"], signer=r["signer"][:8]) for r in rows if r["kind"] == "withdraw"],
           fleet_wallets_trading=len({r["signer"] for r in fleet}), fleet_trades=len(fleet), fleet_buy_sol=round(sum(r["pool_sol_change"] for r in fleet if r["kind"] == "buy"), 3),
           fleet_sell_sol=round(-sum(r["pool_sol_change"] for r in fleet if r["kind"] == "sell"), 3),
           fleet_result=round(-sum(r["pool_sol_change"] for r in fleet), 3),
           creator_trades=sum(1 for r in rows if r["role"] == "создатель GEKKO" and r["kind"] in ("buy", "sell")),
           others_wallets=len({r["signer"] for r in others}), others_trades=len(others), others_result=round(-sum(r["pool_sol_change"] for r in others), 3),
           first_fleet_trade=min((r["time_utc"] for r in fleet), default=""), last_fleet_trade=max((r["time_utc"] for r in fleet), default=""),
           return_covered=sum(1 for r in wrows if r["returned_sol"] and r["funded_before_first_return"] + r["sells_before_first_return_sol"] - r["buy_sol"] >= r["returned_sol"] * 0.99),
           wallets_with_return=sum(1 for r in wrows if r["returned_sol"]), last_sell_to_return_median=sorted(x["last_sell_to_return_s"] for x in wrows if x["last_sell_to_return_s"] != "")[len([x for x in wrows if x["last_sell_to_return_s"] != ""]) // 2] if any(x["last_sell_to_return_s"] != "" for x in wrows) else "",
           sells_after_withdraw=sum(r["sells_after_withdraw"] for r in wrows),
           x7=next((r for r in wrows if r["wallet"].startswith("7hm4V7g2")), None))
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
