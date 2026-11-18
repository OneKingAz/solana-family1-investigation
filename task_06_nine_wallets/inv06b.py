"""Task 06b (no RPC): analysis of the nine wallets' transactions (inv06 raw): buy sizes, coins and their creators (sol_pools.csv,
sol_watch.csv, sol_pool_rec.jsonl), incoming/outgoing SOL by counterparty (full addresses), timeline by hour.
Out: investigation_task_06/ nine_counterparties.csv, nine_coins.csv, nine_hours.csv, _numbers_b.json"""
import collections, csv, datetime as dt, gzip, json, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_06"
NINE = [r["wallet"] for r in csv.DictReader(open(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv", encoding="utf-8-sig"), delimiter=";")]
N = set(NINE)
WSOL = "So11111111111111111111111111111111111111112"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
# mint -> creator
creator_of = {}
for r in csv.DictReader(open(os.path.join(A, "sol_pools.csv"), encoding="utf-8-sig"), delimiter=";"):
    creator_of[r["mint"]] = r["creator"]
for fn in ("sol_watch.csv",):
    p = os.path.join(A, fn)
    if os.path.exists(p):
        for r in csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"):
            if r.get("mint") and r.get("creator"):
                creator_of.setdefault(r["mint"], r["creator"])
p = os.path.join(A, "sol_pool_rec.jsonl")
if os.path.exists(p):
    for l in open(p, encoding="utf-8"):
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d.get("mint") and d.get("creator"):
            creator_of.setdefault(d["mint"], d["creator"])

txs = {}
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        txs[d["signature"]] = d["tx"]

cp = collections.defaultdict(lambda: [0, 0.0, None, None])  # (wallet, dir, other) -> n, sol, first, last
buys = collections.defaultdict(list)  # wallet -> [(unix, cost, mint)]
coin_rows = collections.defaultdict(lambda: dict(buys=0, cost=0.0, wallets=set(), first=None, last=None))
hours = collections.defaultdict(lambda: collections.Counter())
second_addr = collections.Counter()
for sig, t in txs.items():
    m = t["meta"]
    if m.get("err"):
        continue
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
    ts = t["blockTime"]
    for w in N & set(keys):
        i = keys.index(w)
        d_sol = (m["postBalances"][i] - m["preBalances"][i]) / 1e9
        pre, post = collections.Counter(), collections.Counter()
        for b in m.get("preTokenBalances") or []:
            if b.get("owner") == w and b["mint"] != WSOL:
                pre[b["mint"]] += float(b["uiTokenAmount"]["uiAmount"] or 0)
        for b in m.get("postTokenBalances") or []:
            if b.get("owner") == w and b["mint"] != WSOL:
                post[b["mint"]] += float(b["uiTokenAmount"]["uiAmount"] or 0)
        got = [mt for mt in set(pre) | set(post) if post[mt] - pre[mt] > 0]
        lost = [mt for mt in set(pre) | set(post) if post[mt] - pre[mt] < 0]
        sys_transfers = []
        for ins in t["transaction"]["message"]["instructions"]:
            p_ = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p_, dict) and p_.get("type") == "transfer" and ins.get("program") == "system":
                inf = p_["info"]
                sys_transfers.append((inf["source"], inf["destination"], int(inf["lamports"]) / 1e9))
        if got and not lost:
            mt = got[0]
            buys[w].append((ts, -d_sol, mt))
            c = coin_rows[mt]
            c["buys"] += 1
            c["cost"] += -d_sol
            c["wallets"].add(w)
            c["first"] = ts if c["first"] is None else min(c["first"], ts)
            c["last"] = ts if c["last"] is None else max(c["last"], ts)
            hours[iso(ts)[:13]]["buys"] += 1
            for a, b, v in sys_transfers:
                if a == w:
                    second_addr[(w, b)] += 1
            continue
        for a, b, v in sys_transfers:
            if a == w:
                k = (w, "out", b)
            elif b == w:
                k = (w, "in", a)
            else:
                continue
            e = cp[k]
            e[0] += 1
            e[1] += v
            e[2] = ts if e[2] is None else min(e[2], ts)
            e[3] = ts if e[3] is None else max(e[3], ts)
# counterparties aggregated over the nine (direction, other)
agg = collections.defaultdict(lambda: [0, 0.0, set(), None, None])
for (w, d_, o), (n, v, a, b) in cp.items():
    e = agg[(d_, o)]
    e[0] += n
    e[1] += v
    e[2].add(w)
    e[3] = a if e[3] is None else min(e[3], a)
    e[4] = b if e[4] is None else max(e[4], b)
rows = sorted([dict(direction="получено от" if d_ == "in" else "отправлено", counterparty=o, transfers=n, sol=round(v, 6), of_nine=len(ws),
                    first_utc=iso(a), last_utc=iso(b), is_creator=int(o in set(creator_of.values()))) for (d_, o), (n, v, ws, a, b) in agg.items()],
              key=lambda r: -r["sol"])
with open(os.path.join(OUT, "nine_counterparties.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(rows)
crow = sorted([dict(mint=mt, creator=creator_of.get(mt, ""), buys=c["buys"], sol_spent=round(c["cost"], 6), of_nine=len(c["wallets"]),
                    first_buy_utc=iso(c["first"]), last_buy_utc=iso(c["last"]), span_s=c["last"] - c["first"]) for mt, c in coin_rows.items()],
              key=lambda r: r["first_buy_utc"])
with open(os.path.join(OUT, "nine_coins.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.DictWriter(f, fieldnames=list(crow[0].keys()), delimiter=";")
    wr.writeheader()
    wr.writerows(crow)
with open(os.path.join(OUT, "nine_hours.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.writer(f, delimiter=";")
    wr.writerow(["hour_utc", "buys_of_nine"])
    for h in sorted(hours):
        wr.writerow([h, hours[h]["buys"]])
allb = [c for w in N for _, c, _ in buys[w]]
by_creator = collections.Counter()
for r in crow:
    by_creator[r["creator"] or "неизвестен"] += r["sol_spent"]
res = dict(buys=len(allb), sol_spent=round(sum(allb), 3), buy_median=round(statistics.median(allb), 5), buy_p90=round(sorted(allb)[int(len(allb) * .9)], 5),
           coins=len(crow), coins_known_creator=sum(1 for r in crow if r["creator"]), coins_all_nine=sum(1 for r in crow if r["of_nine"] == 9),
           sol_by_creator={k: round(v, 3) for k, v in by_creator.most_common()},
           second_addr_unique=len({b for (w, b) in second_addr}), second_addr_per_wallet={w[:8]: len({b for (x, b) in second_addr if x == w}) for w in NINE},
           first=iso(min(t for w in N for t, _, _ in buys[w])), last=iso(max(t for w in N for t, _, _ in buys[w])))
json.dump(res, open(os.path.join(OUT, "_numbers_b.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
for r in rows[:25]:
    print(r)
