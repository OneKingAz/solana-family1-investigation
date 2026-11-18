"""Task 07 fix (analyst): fetch every FAILED transaction of the nine wallets (inv07_sigs.json, err=True) and record the real network fee
paid, fee payer, signers, error, the program whose instruction failed and its last log line. Helius, HELIUS_KEY of D:\\bot\\.env (not printed).
Resumable: analysis/inv07_failed.jsonl. Out: investigation_task_07/failed_transactions.csv + _failed.json"""
import collections, csv, datetime as dt, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_07"
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


S = json.load(open(os.path.join(A, "inv07_sigs.json"), encoding="utf-8"))
wallets_of = collections.defaultdict(set)
for w, lst in S.items():
    for x in lst:
        if x["err"]:
            wallets_of[x["signature"]].add(w)
RAW = os.path.join(A, "inv07_failed.jsonl")
done = {}
if os.path.exists(RAW):
    for l in open(RAW, encoding="utf-8"):
        d = json.loads(l)
        done[d["signature"]] = d
todo = sorted(set(wallets_of) - set(done))
print(f"ошибочных уникальных {len(wallets_of)}, уже есть {len(done)}, качаю {len(todo)}", flush=True)
lockw = threading.Lock()


def fetch(sig):
    t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not t:
        return
    m = t["meta"]
    ak = t["transaction"]["message"]["accountKeys"]
    keys = [k["pubkey"] for k in ak]
    err = m.get("err")
    failed_prog = ""
    if isinstance(err, dict) and "InstructionError" in err:
        idx = err["InstructionError"][0]
        ins = t["transaction"]["message"]["instructions"]
        if idx < len(ins):
            failed_prog = ins[idx].get("programId") or ins[idx].get("program") or ""
    logs = m.get("logMessages") or []
    errlog = next((l for l in reversed(logs) if "Error" in l or "failed" in l or "error" in l), logs[-1] if logs else "")
    d = dict(signature=sig, slot=t["slot"], blockTime=t["blockTime"], fee_payer=keys[0], signers=[k["pubkey"] for k in ak if k.get("signer")],
             fee_lamports=m["fee"], payer_change_lamports=m["postBalances"][0] - m["preBalances"][0], err=json.dumps(err), failed_program=failed_prog,
             error_log=errlog[:240], programs=sorted({i.get("programId") or i.get("program") or "" for i in t["transaction"]["message"]["instructions"]}))
    with lockw:
        with open(RAW, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
        done[sig] = d


with ThreadPoolExecutor(6) as ex:
    for i, _ in enumerate(ex.map(fetch, todo), 1):
        if i % 1000 == 0:
            print(f"  {i}/{len(todo)}, запросов {CALLS[0]}", flush=True)
rows = []
for sig, d in sorted(done.items(), key=lambda kv: (kv[1]["slot"], kv[0])):
    rows.append(dict(signature=sig, slot=d["slot"], time_utc=iso(d["blockTime"]), wallets=" ".join(sorted(wallets_of.get(sig, []))), fee_payer=d["fee_payer"],
                     fee_sol=d["fee_lamports"] / 1e9, payer_sol_change=d["payer_change_lamports"] / 1e9, failed_program=d["failed_program"], err=d["err"],
                     error_log=d["error_log"]))
with open(os.path.join(OUT, "failed_transactions.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(rows)
fee_by_payer = collections.Counter()
for r in rows:
    fee_by_payer[r["fee_payer"]] += r["fee_sol"]
errs = collections.Counter()
for r in rows:
    e = r["error_log"]
    for key in ("ExceededSlippage", "slippage", "Slippage", "insufficient", "Insufficient", "custom program error"):
        if key in e:
            e = key
            break
    errs[(r["failed_program"][:8], e[:80])] += 1
res = dict(unique_failed=len(wallets_of), fetched=len(done), not_received=len(set(wallets_of) - set(done)), fee_total_sol=round(sum(r["fee_sol"] for r in rows), 6),
           fee_paid_by_nine_sol=round(sum(v for k, v in fee_by_payer.items() if k in S), 6), fee_by_payer={k[:8]: round(v, 6) for k, v in fee_by_payer.most_common(12)},
           fee_median_lamports=sorted(d["fee_lamports"] for d in done.values())[len(done) // 2] if done else 0,
           errors_top={f"{a} | {b}": n for (a, b), n in errs.most_common(12)}, calls=CALLS[0])
json.dump(res, open(os.path.join(OUT, "_failed.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
