"""Task 06 (18.11, user authorised RPC; analyst's request): the 9 wallets that got exactly 29 SOL from the GEKKO creator and only bought in the
GEKKO pool. Every transaction of each wallet from 2026-11-17T13:30Z to now (Helius, HELIUS_KEY of D:\\bot\\.env, never printed):
SOL change, every token balance change (mint), counterparties of SOL transfers, swaps (pool, side), current SOL and token balances.
Raw: analysis/inv06_raw.jsonl.gz. Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_06\\ nine_tx.csv, nine_summary.csv, _numbers.json"""
import collections, csv, datetime as dt, gzip, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_06"
os.makedirs(OUT, exist_ok=True)
GC = "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
WSOL = "So11111111111111111111111111111111111111112"
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
START = int(dt.datetime(2026, 11, 17, 13, 30, tzinfo=dt.timezone.utc).timestamp())
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


NINE = [r["wallet"] for r in csv.DictReader(open(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv", encoding="utf-8-sig"), delimiter=";")]
RAW = os.path.join(A, "inv06_raw.jsonl.gz")
have = {}
if os.path.exists(RAW):
    with gzip.open(RAW, "rt", encoding="utf-8") as f:
        for l in f:
            d = json.loads(l)
            have[d["signature"]] = d["tx"]
lockw = threading.Lock()


def fetch(sig):
    if sig in have:
        return
    t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if t:
        with lockw:
            with gzip.open(RAW, "at", encoding="utf-8") as f:
                f.write(json.dumps({"signature": sig, "tx": t}) + "\n")
            have[sig] = t


sig_of = {}
for w in NINE:
    out, before = [], None
    while True:
        p = {"limit": 1000}
        if before:
            p["before"] = before
        page = rpc("getSignaturesForAddress", [w, p]) or []
        out += page
        if len(page) < 1000 or (page and (page[-1].get("blockTime") or 0) < START):
            break
        before = page[-1]["signature"]
    sig_of[w] = [s["signature"] for s in out if (s.get("blockTime") or 0) >= START and not s.get("err")]
    print(f"{w[:8]}: транзакций с 13:30 UTC 17.11: {len(sig_of[w])} (всего в истории просмотрено {len(out)})", flush=True)
allsig = sorted({s for v in sig_of.values() for s in v})
with ThreadPoolExecutor(6) as ex:
    list(ex.map(fetch, allsig))
print("скачано транзакций", len(have), "запросов", CALLS[0], flush=True)

rows = []
for w in NINE:
    for sig in sig_of[w]:
        t = have.get(sig)
        if not t:
            continue
        m = t["meta"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
        if w not in keys:
            continue
        i = keys.index(w)
        d_sol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
        pre = collections.Counter()
        post = collections.Counter()
        for b in m.get("preTokenBalances") or []:
            if b.get("owner") == w:
                pre[b["mint"]] += float(b["uiTokenAmount"]["uiAmount"] or 0)
        for b in m.get("postTokenBalances") or []:
            if b.get("owner") == w:
                post[b["mint"]] += float(b["uiTokenAmount"]["uiAmount"] or 0)
        tok = {mt: round(post[mt] - pre[mt], 6) for mt in set(pre) | set(post) if abs(post[mt] - pre[mt]) > 1e-9}
        logs = " ".join(m.get("logMessages") or [])
        transfers = []
        for ins in t["transaction"]["message"]["instructions"]:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type") == "transfer" and ins.get("program") == "system":
                inf = p["info"]
                if w in (inf.get("source"), inf.get("destination")):
                    transfers.append((inf["source"], inf["destination"], int(inf["lamports"]) / 1e9))
        wsol_d = tok.pop(WSOL, 0)
        kind = "swap" if AMM in keys or "Instruction: Buy" in logs or "Instruction: Sell" in logs else ("transfer" if transfers else "other")
        coin_mints = [mt for mt in tok]
        side = ""
        if kind == "swap" and coin_mints:
            side = "buy" if tok[coin_mints[0]] > 0 else "sell"
        rows.append(dict(wallet=w, signature=sig, slot=t["slot"], time_utc=iso(t["blockTime"]), unix=t["blockTime"], kind=kind, side=side,
                         sol_change=round(d_sol, 9), wsol_change=round(wsol_d, 9), token_changes=json.dumps(tok, ensure_ascii=False),
                         transfers=json.dumps([(a[:8], b[:8], v) for a, b, v in transfers]), signer=keys[0],
                         counterparty_gekko=int(any(GC in (a, b) for a, b, _ in transfers))))
rows.sort(key=lambda r: (r["wallet"], r["slot"]))
with open(os.path.join(OUT, "nine_tx.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(rows)

# summary per wallet + current balances
summ = []
for w in NINE:
    rs = [r for r in rows if r["wallet"] == w]
    bal = rpc("getBalance", [w]) or {}
    toks = rpc("getTokenAccountsByOwner", [w, {"programId": "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"}, {"encoding": "jsonParsed"}]) or {}
    toks2 = rpc("getTokenAccountsByOwner", [w, {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"}, {"encoding": "jsonParsed"}]) or {}
    held = []
    for a in (toks.get("value") or []) + (toks2.get("value") or []):
        inf = a["account"]["data"]["parsed"]["info"]
        amt = float(inf["tokenAmount"]["uiAmount"] or 0)
        if amt > 0:
            held.append(f"{inf['mint'][:8]}:{amt:g}")
    mints = collections.Counter()
    for r in rs:
        for mt, v in json.loads(r["token_changes"]).items():
            mints[mt] += 1
    cps = collections.Counter()
    for r in rs:
        for a, b, v in json.loads(r["transfers"]):
            cps[(a, b)] += v
    summ.append(dict(wallet=w, txs=len(rs), swaps=sum(1 for r in rs if r["kind"] == "swap"), buys=sum(1 for r in rs if r["side"] == "buy"),
                     sells=sum(1 for r in rs if r["side"] == "sell"), sol_change_total=round(sum(r["sol_change"] for r in rs), 6),
                     coins_traded=len(mints), top_coins=" ".join(f"{m[:8]}×{n}" for m, n in mints.most_common(4)),
                     sol_transfers=" ".join(f"{a}->{b}:{round(v, 3)}" for (a, b), v in cps.most_common(6)),
                     sol_now=round((bal.get("value") or 0) / 1e9, 6), tokens_now=" ".join(held[:6]),
                     first_utc=rs[0]["time_utc"] if rs else "", last_utc=rs[-1]["time_utc"] if rs else ""))
with open(os.path.join(OUT, "nine_summary.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(summ[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(summ)
json.dump(dict(calls=CALLS[0], txs=len(rows), summary=summ), open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for s in summ:
    print(s)
print("запросов Helius:", CALLS[0])
