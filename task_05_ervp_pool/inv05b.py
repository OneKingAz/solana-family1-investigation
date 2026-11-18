"""Task 05b (no RPC): SOL balance of each of the 109 fleet wallets right before its first ErVpTsjX trade and right after its last one
(pre/postBalances of the signer in the raw transactions of inv05), compared with its return in series 1 (14:03:22-23).
Out: investigation_task_05/ervp_balances.csv"""
import csv, gzip, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_05"
GC = "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
W = {r["wallet"] for r in csv.DictReader(open(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_03\park_wallet_flows.csv", encoding="utf-8-sig"), delimiter=";")}
first, last = {}, {}
with gzip.open(os.path.join(A, "inv05_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for l in f:
        t = json.loads(l)["tx"]
        m = t["meta"]
        if m.get("err"):
            continue
        s = t["transaction"]["message"]["accountKeys"][0]
        s = s["pubkey"] if isinstance(s, dict) else s
        if s not in W:
            continue
        if s not in first or t["slot"] < first[s][0]:
            first[s] = (t["slot"], m["preBalances"][0] / 1e9)
        if s not in last or t["slot"] > last[s][0]:
            last[s] = (t["slot"], m["postBalances"][0] / 1e9)
r1 = {}
for r in csv.DictReader(open(os.path.join(A, "sol_export_transfers.csv"), encoding="utf-8-sig"), delimiter=";"):
    if r["asset"] == "SOL" and r["in_trade"] != "True" and r["destination"] == GC and r["source"] in W and 470560352 <= int(r["slot"]) <= 470560356:
        r1[r["source"]] = float(r["amount"])
rows = [dict(wallet=w, slot_first_trade=first[w][0], sol_before_first_trade=round(first[w][1], 9), slot_last_trade=last[w][0],
             sol_after_last_trade=round(last[w][1], 9), return_series1_sol=r1.get(w, ""),
             left_on_wallet=round(last[w][1] - r1.get(w, 0), 9)) for w in sorted(first)]
with open(os.path.join(OUT, "ervp_balances.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(rows)
d = sorted(r["left_on_wallet"] for r in rows)
print(len(rows), "до", round(sum(r["sol_before_first_trade"] for r in rows), 6), "после", round(sum(r["sol_after_last_trade"] for r in rows), 6),
      "возврат", round(sum(r1.values()), 6), "осталось мин/медиана/макс", d[0], d[len(d) // 2], d[-1])
