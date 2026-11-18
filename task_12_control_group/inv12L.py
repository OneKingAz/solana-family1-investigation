"""Task 12 — large-pool stratum. From the pools skipped in inv12 (> 5000 tx up to the nine's last trade), 3 drawn at random (seed 121);
for each, ALL signatures from pool creation to the nine's last trade are listed, and 2500 transactions spread EVENLY over that history
(every k-th by slot) are fetched into the same cache analysis/inv12_raw.jsonl.gz (tag "mint"). Helius, HELIUS_KEY of D:\\bot\\.env, never printed.
Writes analysis/inv12L_pools.json: {mint: {total_tx, fetched, window_end_utc}}."""
import csv, gzip, json, os, random, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
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


NINE = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))}
legs = [l for l in rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv")) if l["signer"] in NINE and l["mint"]]
pool_of, last_sig, last_slot = {}, {}, {}
for l in legs:
    pool_of[l["mint"]] = l["pool"]
    if l["mint"] not in last_slot or int(l["slot"]) > last_slot[l["mint"]]:
        last_slot[l["mint"]], last_sig[l["mint"]] = int(l["slot"]), l["signature"]
SKIPPED = ["Ejt4zzZZV4ESdvCoJhR91NeY5VgAj9rG457iJpD2zh7Z", "FkCw8RkTEjRhxk9VeXptFPr31uMtC1S9RtvGmor7JsmF", "B1tuLdRMpJNwNxA8H9635RrR45vAUDRpvqZmV2czc2ya",
           "6rLXB5Pk5zKVwfFZEDTg2zdxxH99PdHR7sNNZL3qpigu", "BvcKi8kZrMb7NtVee5iQayVgrKF7smGskNvKPAC5atT5", "2B9G7wnvKmgXJYJQEdA5wdMWzzMt1cEW93Sq88JvrVw2",
           "HnsjuKvA7zrRxme9bQJphh9eegWGxouaeYemwiCpdTFz", "6Jz27UEKUDmVzd3tEkj753evtZ8ibJhGiArLvucYcWWa", "AFnDc2Bs7Ti62NtTYGUL7Cex3Ve28m5DvzodP4sbu2PL",
           "GtVUBcQAxrB39vim7rp1TMtdDKxbeQ9eSufuCtNf4Vx3"]
random.seed(121)
PICK = random.sample(sorted(SKIPPED), 3)
RAW = os.path.join(A, "inv12_raw.jsonl.gz")
have = set()
with gzip.open(RAW, "rt", encoding="utf-8") as f:
    for line in f:
        have.add(json.loads(line)["signature"])
info = {}
lockw = threading.Lock()
for m in PICK:
    out, before = [], last_sig[m]
    while True:
        page = rpc("getSignaturesForAddress", [pool_of[m], {"before": before, "limit": 1000}]) or []
        out += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    ok = sorted([x for x in out if not x.get("err")], key=lambda x: x["slot"])
    # analyst: not the first 2500 (one part of the history) but 2500 spread evenly over the whole history up to the nine's last trade
    step = max(1, len(ok) / 2500)
    win = [ok[int(i * step)] for i in range(min(2500, len(ok)))]
    info[m] = dict(pool=pool_of[m], total_tx=len(ok) + 1, fetched=len(win), window_end_slot=win[-1]["slot"] if win else None,
                   window_end_time=win[-1].get("blockTime") if win else None)
    info[m]["sampling"] = f"каждая {step:.2f}-я по слоту, равномерно по всей истории"
    print(m[:8], "всего", len(ok) + 1, "беру равномерно", len(win), flush=True)

    def fetch(sig, m=m):
        if sig in have:
            return
        t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if t:
            with lockw:
                with gzip.open(RAW, "at", encoding="utf-8") as f:
                    f.write(json.dumps({"signature": sig, "mint": m, "tx": t}) + "\n")
                have.add(sig)

    with ThreadPoolExecutor(6) as ex:
        list(ex.map(fetch, [x["signature"] for x in win]))
json.dump(info, open(os.path.join(A, "inv12L_pools.json"), "w", encoding="utf-8"), indent=1)
print("готово, запросов", CALLS[0])
