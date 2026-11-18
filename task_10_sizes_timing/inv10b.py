"""Task 10b (no RPC): for every swap tx of the nine — pool reserves before the tx (preTokenBalances of the pool's vaults), expected coin out by
x*y=k without fee, actual out / expected, M (minimum out, buy argument 2) / expected, buy / pool WSOL reserve, buy / wallet SOL balance before the tx,
size regime by time. Out: investigation_task_10/reserve_check.csv"""
import csv, gzip, json, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
O = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_10"
WSOL = "So11111111111111111111111111111111111111112"
R = {r["signature"]: r for r in csv.DictReader(open(os.path.join(O, "tx_sizes.csv"), encoding="utf-8-sig"), delimiter=";")}
rows, seen = [], set()
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        s = d["signature"]
        if s not in R or s in seen:
            continue
        seen.add(s)
        r, m = R[s], d["tx"]["meta"]
        pre = {(b.get("owner"), b["mint"]): int(b["uiTokenAmount"]["amount"]) for b in m["preTokenBalances"]}
        x = int(round(float(r["buy_sol"]) * 1e9))
        row = dict(signature=s, program=r["program"], time_utc=r["time_utc"], wallet=r["wallet"], mint=r["mint"], buy_sol=r["buy_sol"],
                   regime="B 1.5–3.1" if "2026-11-18T02" <= r["time_utc"] < "2026-11-18T13" else "A 3–6.6",
                   wallet_sol_before=m["preBalances"][0] / 1e9, buy_to_wallet_balance=x / m["preBalances"][0] if m["preBalances"][0] else "")
        if r["program"] == "PumpSwap":
            ws, cn = pre.get((r["pool"], WSOL)), pre.get((r["pool"], r["mint"]))
            if ws and cn:
                gross = cn * x // (ws + x)
                row.update(pool_wsol_before=ws / 1e9, pool_coin_before_raw=cn, expected_out_raw=gross, actual_over_expected=int(r["buy_tokens_raw"]) / gross,
                           minout_over_expected=int(r["buy_arg2"]) / gross, buy_to_pool_pct=100 * x / ws)
        rows.append(row)
keys = sorted({k for r in rows for k in r}, key=lambda k: list(rows[0].keys()).index(k) if k in rows[0] else 99)
with open(os.path.join(O, "reserve_check.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=keys, delimiter=";")
    w.writeheader()
    w.writerows(rows)
ps = [r for r in rows if "actual_over_expected" in r]
q = lambda z, p: sorted(z)[int(p * len(z))]
for k in ("actual_over_expected", "minout_over_expected", "buy_to_pool_pct"):
    v = [r[k] for r in ps]
    print(k, "медиана", round(statistics.median(v), 6), "p10", round(q(v, .1), 6), "p90", round(q(v, .9), 6), "мин", round(min(v), 6), "макс", round(max(v), 6))
for reg in ("A 3–6.6", "B 1.5–3.1"):
    v = [r for r in rows if r["regime"] == reg and r["program"] == "PumpSwap"]
    print(reg, len(v), "покупка мин", min(float(r["buy_sol"]) for r in v), "макс", max(float(r["buy_sol"]) for r in v),
          "покупка/баланс медиана", round(statistics.median(r["buy_to_wallet_balance"] for r in v), 4), "макс", round(max(r["buy_to_wallet_balance"] for r in v), 4))
