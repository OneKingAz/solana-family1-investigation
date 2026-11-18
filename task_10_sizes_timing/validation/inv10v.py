"""Task 10 — independent validation (analyst's request). No RPC, no change to task 10 files.
1) minout_sell_match.csv: per PumpSwap tx buy_arg2 (minimum out), sell_arg1, coin actually sent to the pool, coin fee paid by the wallet on the sell,
   explicit equality flags; every mismatch explained from the leg data.
2) regime_change_analysis.csv: exact switch times of the buy-size floor from the ordered sequence (slot, tx) — globally and per wallet; buys < 3.05 SOL
   occur only in the low regime, buys > 3.11 SOL only in the high one; the 12:00–13:00 transition listed tx by tx.
3) timing_by_wallet.csv: per wallet intervals between its consecutive trades: same coin / different coin; zero-second intervals counted (blockTime is 1 s).
4) coin_sessions.csv: activity of the nine per coin split into sessions with gap thresholds 60/120/180 s vs first-to-last span.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_10\\validation\\"""
import collections, csv, datetime as dt, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, r"investigation_task_10\validation")
os.makedirs(OUT, exist_ok=True)
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
TX = rd(os.path.join(D, r"investigation_task_10\tx_sizes.csv"))
LEGS = rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv"))
sell_leg = {l["signature"]: l for l in LEGS if l["side"] == "SELL"}
buy_leg = {l["signature"]: l for l in LEGS if l["side"] == "BUY"}


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))] if v else ""


# ---------- 1 ----------
m_rows, mism = [], []
for r in TX:
    if r["program"] != "PumpSwap":
        continue
    s = sell_leg[r["signature"]]
    b2, s1 = int(r["buy_arg2"]), int(r["sell_arg1"])
    to_pool, fee = int(s["coin_to_pool_raw"]), int(s["fee_coin_raw"] or 0)
    got = int(buy_leg[r["signature"]]["coin_from_pool_raw"])
    row = dict(signature=r["signature"], wallet=r["wallet"], mint=r["mint"], slot=r["slot"], time_utc=r["time_utc"], buy_arg2_min_out=b2, sell_arg1=s1,
               coin_received_on_buy=got, coin_to_pool_on_sell=to_pool, coin_fee_paid_on_sell=fee, to_pool_plus_fee=to_pool + fee,
               eq_buyarg2_sellarg1=int(b2 == s1), eq_sellarg1_to_pool_plus_fee=int(s1 == to_pool + fee), eq_sellarg1_to_pool=int(s1 == to_pool),
               diff_sellarg1_minus_to_pool_plus_fee=s1 - (to_pool + fee), received_minus_min_out=got - b2)
    m_rows.append(row)
    if not row["eq_sellarg1_to_pool_plus_fee"] or not row["eq_buyarg2_sellarg1"]:
        mism.append(row)
wcsv("minout_sell_match.csv", m_rows)

# ---------- 2 ----------
ps = sorted([r for r in TX if r["program"] == "PumpSwap"], key=lambda r: (int(r["slot"]), r["signature"]))
LOW_MAX, HIGH_MIN = 3.05, 3.11  # observed: high regime never below 3.0546, low regime never above 3.10


def cls(x):
    return "low-only" if x < LOW_MAX else "high-only" if x > HIGH_MIN else "overlap"


switch = []
prev = None  # last definite regime and its tx
for r in ps:
    c = cls(float(r["buy_sol"]))
    if c == "overlap":
        continue
    reg = c.split("-")[0]
    if prev and prev[0] != reg:
        switch.append(dict(scope="все девять", from_regime=prev[0], to_regime=reg, last_tx_before=prev[1]["signature"], last_before_utc=prev[1]["time_utc"],
                           last_before_slot=prev[1]["slot"], last_before_buy_sol=prev[1]["buy_sol"], first_tx_after=r["signature"], first_after_utc=r["time_utc"],
                           first_after_slot=r["slot"], first_after_buy_sol=r["buy_sol"], gap_s=int(r["unix"]) - int(prev[1]["unix"])))
    prev = (reg, r)
per_w = []
for w in sorted({r["wallet"] for r in ps}):
    prev = None
    for r in [x for x in ps if x["wallet"] == w]:
        c = cls(float(r["buy_sol"]))
        if c == "overlap":
            continue
        reg = c.split("-")[0]
        if prev and prev[0] != reg:
            per_w.append(dict(scope=w, from_regime=prev[0], to_regime=reg, last_tx_before=prev[1]["signature"], last_before_utc=prev[1]["time_utc"],
                              last_before_slot=prev[1]["slot"], last_before_buy_sol=prev[1]["buy_sol"], first_tx_after=r["signature"], first_after_utc=r["time_utc"],
                              first_after_slot=r["slot"], first_after_buy_sol=r["buy_sol"], gap_s=int(r["unix"]) - int(prev[1]["unix"])))
        prev = (reg, r)
wcsv("regime_change_analysis.csv", switch + per_w)
trans = [dict(time_utc=r["time_utc"], slot=r["slot"], wallet=r["wallet"][:8], mint=r["mint"][:8], buy_sol=r["buy_sol"], regime=cls(float(r["buy_sol"])))
         for r in ps if "2026-11-18T12:00" <= r["time_utc"] < "2026-11-18T13:00"]
wcsv("transition_12_13.csv", trans)
# mixing check: within the low window, any high-only buy? (and vice versa)
lowwin = [s for s in switch if s["to_regime"] == "low"]
highwin = [s for s in switch if s["to_regime"] == "high"]

# ---------- 3 ----------
allrows = sorted(TX, key=lambda r: (int(r["slot"]), r["signature"]))
t_rows = []
for w in sorted({r["wallet"] for r in allrows}):
    seq = [r for r in allrows if r["wallet"] == w]
    same, diff, zero_same, same_slot = [], [], 0, 0
    for a, b in zip(seq, seq[1:]):
        g = int(b["unix"]) - int(a["unix"])
        if a["slot"] == b["slot"]:
            same_slot += 1
        (same if a["mint"] == b["mint"] else diff).append(g)
        zero_same += g == 0
    st = lambda v, p: q(v, p) if v else ""
    t_rows.append(dict(wallet=w, trades=len(seq), same_coin_n=len(same), same_min=min(same) if same else "", same_median=statistics.median(same) if same else "",
                       same_mean=round(statistics.mean(same), 2) if same else "", same_p75=st(same, .75), same_p90=st(same, .9), same_max=max(same) if same else "",
                       diff_coin_n=len(diff), diff_min=min(diff) if diff else "", diff_median=statistics.median(diff) if diff else "", diff_mean=round(statistics.mean(diff), 2) if diff else "",
                       diff_p75=st(diff, .75), diff_p90=st(diff, .9), zero_second_intervals=zero_same, consecutive_in_same_slot=same_slot))
wcsv("timing_by_wallet.csv", t_rows)
# interleaving of coins by the nine together, exact order (slot, signature within slot is NOT execution order: same-slot pairs counted separately)
switches = back = 0
seq_all = [(int(r["slot"]), r["mint"], r["unix"]) for r in allrows]
last_coin, seen_coins = None, []
alt_same_slot = 0
for i in range(1, len(seq_all)):
    a, b = seq_all[i - 1], seq_all[i]
    if a[1] != b[1]:
        switches += 1
        if a[0] == b[0]:
            alt_same_slot += 1
        # back-and-forth: b's coin seen within the previous 10 trades but not the immediately previous coin
        prevs = [x[1] for x in seq_all[max(0, i - 10):i - 1]]
        if b[1] in prevs:
            back += 1

# ---------- 4 ----------
by_coin = collections.defaultdict(list)
for r in allrows:
    by_coin[r["mint"]].append(int(r["unix"]))
s_rows = []
for mt, ts in by_coin.items():
    ts.sort()
    row = dict(mint=mt, trades=len(ts), first_utc=iso(ts[0]), last_utc=iso(ts[-1]), span_first_to_last_s=ts[-1] - ts[0], max_gap_s=max([b - a for a, b in zip(ts, ts[1:])] or [0]))
    for th in (60, 120, 180):
        ss, cur = [], [ts[0]]
        for t in ts[1:]:
            if t - cur[-1] > th:
                ss.append(cur)
                cur = [t]
            else:
                cur.append(t)
        ss.append(cur)
        row[f"sessions_gap{th}"] = len(ss)
        row[f"longest_session_gap{th}_s"] = max(s[-1] - s[0] for s in ss)
        row[f"total_active_gap{th}_s"] = sum(s[-1] - s[0] for s in ss)
    s_rows.append(row)
s_rows.sort(key=lambda r: r["first_utc"])
wcsv("coin_sessions.csv", s_rows)

res = dict(pumpswap_tx=len(m_rows), eq_buyarg2_sellarg1=sum(r["eq_buyarg2_sellarg1"] for r in m_rows),
           eq_sellarg1_to_pool_plus_fee=sum(r["eq_sellarg1_to_pool_plus_fee"] for r in m_rows), eq_sellarg1_to_pool=sum(r["eq_sellarg1_to_pool"] for r in m_rows),
           mismatches=mism, regime_switches_global=switch, per_wallet_switches=len(per_w),
           per_wallet_switch_times={k: sorted({(s["from_regime"] + "→" + s["to_regime"], s["first_after_utc"]) for s in per_w if s["to_regime"] == k}) for k in ("low", "high")},
           coin_switches_consecutive=switches, coin_switch_back_within_10=back, coin_switch_in_same_slot=alt_same_slot,
           sessions={th: dict(coins_split=sum(1 for r in s_rows if r[f"sessions_gap{th}"] > 1), sessions_total=sum(r[f"sessions_gap{th}"] for r in s_rows),
                              longest_median=statistics.median(r[f"longest_session_gap{th}_s"] for r in s_rows)) for th in (60, 120, 180)},
           span_median=statistics.median(r["span_first_to_last_s"] for r in s_rows))
import json
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k not in ("per_wallet_switch_times",)}, ensure_ascii=False, indent=1, default=str)[:6000])
print(json.dumps(res["per_wallet_switch_times"], ensure_ascii=False, indent=1))
