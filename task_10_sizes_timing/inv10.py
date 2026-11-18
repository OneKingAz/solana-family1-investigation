"""Task 10: sizes and timing of the nine wallets' trades. No RPC. Input: investigation_task_07/nine_swap_legs.csv (decoded legs, raw amounts),
inv06_raw.jsonl.gz (instruction data -> arguments: amount in, minimum out = slippage the bot sets), inv07_sigs.json.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_10\\"""
import collections, csv, datetime as dt, gzip, json, math, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
T7 = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_07"
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_10"
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b


NINE = [r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv")]
N = set(NINE)
legs = [l for l in rd(os.path.join(T7, "nine_swap_legs.csv")) if l["signer"] in N]
want = {l["signature"] for l in legs}
# instruction arguments
args = {}  # (sig, ix_index) -> (u64, u64[, ...])
seen = set()
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        sig = d["signature"]
        if sig not in want or sig in seen:
            continue
        seen.add(sig)
        for i, ins in enumerate(d["tx"]["transaction"]["message"]["instructions"]):
            if ins.get("programId") in (AMM, MET) and "data" in ins:
                raw = b58dec(ins["data"])
                vals = [int.from_bytes(raw[8 + 8 * k:16 + 8 * k], "little") for k in range((len(raw) - 8) // 8)]
                args[(sig, i)] = (raw[:8].hex(), vals, len(raw))
# per transaction
tx = collections.defaultdict(dict)
for l in legs:
    tx[l["signature"]][l["side"]] = l
rows = []
for sig, d in tx.items():
    b, s = d.get("BUY"), d.get("SELL")
    if not b or not s:
        continue
    dec = int(b["coin_decimals"] or 0)
    ab = args.get((sig, int(b["ix_index"])), ("", [], 0))
    as_ = args.get((sig, int(s["ix_index"])), ("", [], 0))
    buy_w = int(b["wsol_to_pool_raw"])
    buy_c = int(b["coin_from_pool_raw"])
    sell_c = int(s["coin_to_pool_raw"]) + int(s["fee_coin_raw"] or 0)
    sell_w = int(s["wsol_from_pool_raw"])
    kept = buy_c - sell_c
    price = buy_w / buy_c if buy_c else 0  # lamports per raw coin unit, buy price
    # argument interpretation (PumpSwap): sell(base_amount_in, min_quote_amount_out); buy_exact_quote_in(spendable_quote_in, min_base_amount_out)
    a1, a2 = (ab[1] + [None, None])[:2]
    s1, s2 = (as_[1] + [None, None])[:2]
    rows.append(dict(signature=sig, wallet=b["signer"], mint=b["mint"], pool=b["pool"], program=b["program"], slot=int(b["slot"]), unix=int(b["blockTime"]),
                     time_utc=b["time_utc"], buy_sol=buy_w / 1e9, buy_tokens_raw=buy_c, sell_tokens_raw=sell_c, sell_sol=sell_w / 1e9, kept_tokens_raw=kept,
                     kept_pct=100 * kept / buy_c if buy_c else None, sold_pct=100 * sell_c / buy_c if buy_c else None, net_sol=(buy_w - sell_w) / 1e9,
                     kept_value_sol_at_buy_price=kept * price / 1e9, decimals=dec,
                     buy_disc=ab[0], buy_arg1=a1, buy_arg2=a2, sell_disc=as_[0], sell_arg1=s1, sell_arg2=s2,
                     buy_arg1_equals_wsol_in=int(a1 == buy_w) if a1 is not None else "", buy_min_out_ratio=(a2 / buy_c) if a2 and buy_c else "",
                     sell_arg1_equals_coin_in=int(s1 == int(s["coin_to_pool_raw"])) if s1 is not None else "",
                     sell_arg1_equals_coin_in_plus_fee=int(s1 == sell_c) if s1 is not None else "",
                     sell_min_out_ratio=(s2 / sell_w) if s2 and sell_w else ""))
rows.sort(key=lambda r: (r["slot"], r["signature"]))


def wcsv(name, rs):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rs)


wcsv("tx_sizes.csv", rows)


def dist(x):
    x = sorted(v for v in x if v is not None and v != "")
    if not x:
        return {}
    q = lambda p: x[min(len(x) - 1, int(p * len(x)))]
    m = statistics.mean(x)
    return dict(n=len(x), min=x[0], p10=q(.1), median=statistics.median(x), mean=m, p75=q(.75), p90=q(.9), max=x[-1],
                cv=(statistics.pstdev(x) / m) if m else None)


def rnd(d, k=6):
    return {a: (round(b, k) if isinstance(b, float) else b) for a, b in d.items()}


PS = [r for r in rows if r["program"] == "PumpSwap"]
MT = [r for r in rows if r["program"] != "PumpSwap"]
res = {}
for name, R in (("PumpSwap", PS), ("Meteora", MT)):
    res[name] = dict(txs=len(R), buy_sol=rnd(dist([r["buy_sol"] for r in R])), net_sol=rnd(dist([r["net_sol"] for r in R]), 8),
                     kept_pct=rnd(dist([r["kept_pct"] for r in R]), 5), sold_pct=rnd(dist([r["sold_pct"] for r in R]), 5),
                     kept_value_sol=rnd(dist([r["kept_value_sol_at_buy_price"] for r in R]), 8),
                     common_buy_sol_0_01=collections.Counter(round(r["buy_sol"], 2) for r in R).most_common(8),
                     identical_buy_lamports_share=round(1 - len({int(r["buy_sol"] * 1e9) for r in R}) / max(1, len(R)), 5),
                     buy_arg1_is_wsol_in=sum(1 for r in R if r["buy_arg1_equals_wsol_in"] == 1),
                     sell_arg1_is_coin_in=sum(1 for r in R if r["sell_arg1_equals_coin_in"] == 1),
                     sell_arg1_is_coin_in_plus_fee=sum(1 for r in R if r["sell_arg1_equals_coin_in_plus_fee"] == 1),
                     buy_min_out_ratio=rnd(dist([r["buy_min_out_ratio"] for r in R]), 6), sell_min_out_ratio=rnd(dist([r["sell_min_out_ratio"] for r in R]), 6),
                     buy_args_n=collections.Counter(len(args.get((r["signature"], 0), ("", []))[1]) for r in R).most_common(3))
# buy-size histogram (PumpSwap), 0.25 SOL bins
hist = collections.Counter(math.floor(r["buy_sol"] * 4) / 4 for r in PS)
with open(os.path.join(OUT, "buy_size_histogram.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["buy_sol_from", "buy_sol_to", "txs"])
    for k in sorted(hist):
        w.writerow([k, k + 0.25, hist[k]])
# per wallet / per coin
by_w = []
for wlt in NINE:
    R = [r for r in PS if r["wallet"] == wlt]
    d1, d2, d3 = dist([r["buy_sol"] for r in R]), dist([r["kept_pct"] for r in R]), dist([r["net_sol"] for r in R])
    by_w.append(dict(wallet=wlt, txs=len(R), coins=len({r["mint"] for r in R}), buy_sol_min=round(d1["min"], 6), buy_sol_median=round(d1["median"], 6),
                     buy_sol_mean=round(d1["mean"], 6), buy_sol_p75=round(d1["p75"], 6), buy_sol_p90=round(d1["p90"], 6), buy_sol_max=round(d1["max"], 6), buy_sol_cv=round(d1["cv"], 4),
                     kept_pct_median=round(d2["median"], 5), kept_pct_p10=round(d2["p10"], 5), kept_pct_p90=round(d2["p90"], 5), kept_pct_cv=round(d2["cv"], 4),
                     net_sol_median=round(d3["median"], 8), net_sol_cv=round(d3["cv"], 4)))
wcsv("sizes_by_wallet.csv", by_w)
by_c = []
for mt in sorted({r["mint"] for r in PS}):
    R = [r for r in PS if r["mint"] == mt]
    d1, d2, d3 = dist([r["buy_sol"] for r in R]), dist([r["kept_pct"] for r in R]), dist([r["net_sol"] for r in R])
    ts = sorted(r["unix"] for r in R)
    by_c.append(dict(mint=mt, txs=len(R), wallets=len({r["wallet"] for r in R}), first_utc=iso(ts[0]), last_utc=iso(ts[-1]), session_s=ts[-1] - ts[0],
                     buy_sol_median=round(d1["median"], 6), buy_sol_cv=round(d1["cv"], 4), buy_sol_total=round(sum(r["buy_sol"] for r in R), 4),
                     kept_pct_median=round(d2["median"], 5), kept_pct_cv=round(d2["cv"], 4), net_sol_total=round(sum(r["net_sol"] for r in R), 6),
                     net_sol_median=round(d3["median"], 8)))
by_c.sort(key=lambda r: r["first_utc"])
wcsv("sizes_by_coin.csv", by_c)
# within-coin trend: does kept% / buy size change with time since the coin's first nine-buy? (deciles)
first_t = {c["mint"]: int(dt.datetime.strptime(c["first_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp()) for c in by_c}
trend = collections.defaultdict(list)
for r in PS:
    age = r["unix"] - first_t[r["mint"]]
    b = min(age // 60, 30)
    trend[b].append(r)
tr = [dict(minute_since_nine_first_buy=k if k < 30 else "30+", txs=len(v), buy_sol_median=round(statistics.median(x["buy_sol"] for x in v), 4),
           kept_pct_median=round(statistics.median(x["kept_pct"] for x in v), 4), net_sol_median=round(statistics.median(x["net_sol"] for x in v), 6))
      for k, v in sorted(trend.items())]
wcsv("trend_by_minute.csv", tr)
# correlation buy size vs kept pct / net sol (Spearman via ranks)


def spearman(x, y):
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0] * len(v)
        for i, j in enumerate(o):
            r[j] = i
        return r
    a, b = rk(x), rk(y)
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((p - ma) * (q - mb) for p, q in zip(a, b))
    return num / math.sqrt(sum((p - ma) ** 2 for p in a) * sum((q - mb) ** 2 for q in b))


res["spearman_buy_vs_kept_pct"] = round(spearman([r["buy_sol"] for r in PS], [r["kept_pct"] for r in PS]), 4)
res["spearman_buy_vs_net_sol"] = round(spearman([r["buy_sol"] for r in PS], [r["net_sol"] for r in PS]), 4)
# timing
gaps_any, gaps_coin, per_hour, parallel = [], [], collections.Counter(), []
for wlt in NINE:
    ts = sorted(r["unix"] for r in rows if r["wallet"] == wlt)
    gaps_any += [b - a for a, b in zip(ts, ts[1:])]
    by_m = collections.defaultdict(list)
    for r in rows:
        if r["wallet"] == wlt:
            by_m[r["mint"]].append(r["unix"])
    for v in by_m.values():
        v.sort()
        gaps_coin += [b - a for a, b in zip(v, v[1:])]
for r in rows:
    per_hour[r["time_utc"][:13]] += 1
# how many coins the nine trade at the same time (per minute)
mins = collections.defaultdict(set)
for r in rows:
    mins[r["unix"] // 60].add(r["mint"])
gap_hist = collections.Counter(min(g, 120) // 5 * 5 for g in gaps_coin)
with open(os.path.join(OUT, "gap_histogram.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["gap_s_from", "gap_s_to", "count_same_wallet_same_coin"])
    for k in sorted(gap_hist):
        w.writerow([k, k + 5 if k < 120 else "∞", gap_hist[k]])
with open(os.path.join(OUT, "activity_by_hour.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["hour_utc", "txs_of_nine"])
    for h in sorted(per_hour):
        w.writerow([h, per_hour[h]])
res["gap_same_wallet_any_coin_s"] = rnd(dist(gaps_any), 2)
res["gap_same_wallet_same_coin_s"] = rnd(dist(gaps_coin), 2)
res["gap_same_coin_mode_5s_bins"] = gap_hist.most_common(6)
res["coins_traded_per_minute"] = dict(sorted(collections.Counter(len(v) for v in mins.values()).items()))
res["session_s_per_coin"] = rnd(dist([c["session_s"] for c in by_c]), 1)
res["txs_per_coin"] = rnd(dist([c["txs"] for c in by_c]), 1)
res["kept_pct_cv_within_wallet_median"] = round(statistics.median(w["kept_pct_cv"] for w in by_w), 4)
res["buy_sol_cv_within_wallet_median"] = round(statistics.median(w["buy_sol_cv"] for w in by_w), 4)
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str))
