"""18.11 (analyst's plan): walk-forward backtest of «enter when the pump fleet of family 1 has arrived». No new node requests.
Data: sol_buyers.csv (every swap of the first 60 s of 40 pools: t from creation, wallet, SOL into/out of the pool, withdraw),
pool creation times from sol_pool_rec.jsonl ('created') / sol_watch_paths.jsonl ('t0', detection ~1 s after creation).
No look-ahead: pools are taken in creation order; for pool i the fleet = wallets that bought >= MIN_BUY SOL (not the creator) in >= 3 EARLIER
pools; the core = the 30 most frequent of them. Pools of the first PRIME pools only build the list (not traded).
Pool SOL over time: 55 SOL (family 1 creation liquidity) + the cumulative SOL flow of the swaps; price ~ SOL^2 (constant product).
Checkpoints 15/20/25 s: N unique fleet bots, their SOL, new bots in the last 5 s, core share.
Signal variants (N, T); entry at T + LAT s; exits: +10 s, +20 s, at 60 s; targets +5/+10/+15 % (else 60 s). A withdraw before the signal =
skipped (avoided); after the entry and before the exit = -100 %. Costs: 0.6 % pool fees + network fees at stake 0.05 SOL ~ 1 % in total.
Splits: by creator, first half / second half of the pools. Out: analysis/sol_backtest.txt, sol_backtest_signals.csv."""
import collections, csv, json, os, statistics as st, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
MIN_BUY, PRIME, LAT, COST, BASE = 0.05, 5, 1.5, 0.01, 55.0
FAM1 = ("6e7XUsDb", "6yf7adkH", "29iqxoNv", "CPC8iEE1", "GLEBhVYd", "8vB8UUGx")
VARIANTS = [(5, 15), (8, 15), (10, 20), (15, 20), (20, 25)]

ev = collections.defaultdict(list)
creator, wd = {}, {}
for r in csv.DictReader(open(os.path.join(HERE, "sol_buyers.csv"), encoding="utf-8-sig"), delimiter=";"):
    ev[r["pool"]].append((float(r["t"]), r["who"], float(r["sol"]), r["kind"]))
    creator[r["pool"]] = r["creator"] or ""
    if r["withdraw_s"] not in ("", "None"):
        wd[r["pool"]] = float(r["withdraw_s"])
t_created = {}
for fn, key, shift in (("sol_pool_rec.jsonl", "created", 0), ("sol_watch_paths.jsonl", "t0", -1)):
    try:
        for l in open(os.path.join(HERE, fn), encoding="utf-8"):
            d = json.loads(l)
            if d["pool"] in ev and d.get(key):
                t_created.setdefault(d["pool"], float(d[key]) + shift)
                if d.get("creator"):
                    creator[d["pool"]] = creator[d["pool"]] or d["creator"]
    except OSError:
        pass
order = sorted((p for p in ev if p in t_created), key=lambda p: t_created[p])
missing = [p for p in ev if p not in t_created]

# v2 (analyst 18.11): the pool's own starting liquidity instead of one BASE for all (8vB8UUGx pools start at ~85 SOL, not 55):
# base = the first SOL value of the recorded path minus the swaps of sol_buyers.csv up to that moment (both from the pool's creation)
# the first path point is the creation itself (before the creator's own buy) and the swap times are whole seconds, so one point is
# ambiguous: base = the median of (path SOL - swaps so far) over the path points of 3-30 s
path_pts = {}
for fn, rel in (("sol_pool_rec.jsonl", 0.0), ("sol_watch_paths.jsonl", 1.0)):  # sol_watch: t from our detection, ~1 s after the creation
    try:
        for l in open(os.path.join(HERE, fn), encoding="utf-8"):
            d = json.loads(l)
            if d["pool"] in ev and d.get("path") and d["pool"] not in path_pts:
                path_pts[d["pool"]] = [(x[0] + rel, x[1]) for x in d["path"]]
    except OSError:
        pass
BASE_OF, BASE_N = {}, {}
for p in ev:
    diffs = [s - sum(e[2] for e in ev[p] if e[0] <= t and e[3] in ("buy", "sell")) for t, s in path_pts.get(p, []) if 3 <= t <= 30 and s > 1]
    BASE_OF[p] = st.median(diffs) if diffs else BASE
    BASE_N[p] = len(diffs)


def sol_at(p, t):
    """pool SOL just after second t (the pool's own base + all swaps up to t); None if withdrawn by then"""
    if p in wd and wd[p] <= t:
        return None
    return BASE_OF[p] + sum(e[2] for e in ev[p] if e[0] <= t and e[3] in ("buy", "sell"))


def ret(p, t_in, t_out):
    s0, s1 = sol_at(p, t_in), sol_at(p, t_out)
    if s0 is None:
        return None
    if s1 is None:
        return -1.0
    return (s1 / s0) ** 2 - 1 - COST


def exit_target(p, t_in, tp, t_max=60):
    s0 = sol_at(p, t_in)
    if s0 is None:
        return None
    for t in sorted({e[0] for e in ev[p] if e[0] > t_in} | {t_max}):
        if t > t_max:
            break
        s = sol_at(p, t)
        if s is None:
            return -1.0
        if (s / s0) ** 2 - 1 >= tp:
            return (s / s0) ** 2 - 1 - COST
    s = sol_at(p, t_max)
    return -1.0 if s is None else (s / s0) ** 2 - 1 - COST


# v2 (analyst 18.11): the fleet is built strictly by time — only buys that happened BEFORE the current pool was created
# (pools can start 2 s apart, and v1 counted the whole first minute of the previous pool)
QBUYS = sorted((t_created[q] + e[0], e[1], q) for q in order for e in ev[q]
               if e[3] == "buy" and e[2] >= MIN_BUY and e[1] != creator.get(q, ""))
recs = []
for i, p in enumerate(order):
    tc = t_created[p]
    pools_by = collections.defaultdict(set)
    for ta, wlt, q in QBUYS:
        if ta >= tc:
            break
        if q != p:
            pools_by[wlt].add(q)
    seen_count = collections.Counter({w: len(s) for w, s in pools_by.items()})
    fleet = {w for w, c in seen_count.items() if c >= 3}
    core = {w for w, _ in seen_count.most_common(30) if w in fleet}
    cr = creator.get(p, "")
    rec = dict(pool=p, creator=cr[:8], fam1=int(cr[:8] in FAM1), idx=i, withdraw=wd.get(p), fleet_known=len(fleet))
    for T in (15, 20, 25):
        bots = [e for e in ev[p] if e[3] == "buy" and e[0] <= T and e[1] in fleet and e[1] != cr]
        uniq = {e[1] for e in bots}
        new5 = {e[1] for e in bots if e[0] > T - 5} - {e[1] for e in bots if e[0] <= T - 5}
        rec[f"N{T}"] = len(uniq)
        rec[f"sol{T}"] = round(sum(e[2] for e in bots), 2)
        rec[f"new5_{T}"] = len(new5)
        rec[f"core{T}"] = round(len(uniq & core) / len(uniq), 2) if uniq else 0
        rec[f"wd_before_{T}"] = int(p in wd and wd[p] <= T)
    rec["base_sol"] = round(BASE_OF[p], 2)
    recs.append(rec)

with open(os.path.join(HERE, "sol_backtest_signals.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(recs[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(recs)

test = [r for r in recs if r["idx"] >= PRIME and r["fam1"]]
L = ["ВЕРСИЯ 2 (18.11, по замечаниям аналитика): парк строго по времени операций; стартовая ликвидность своя у каждого пула. "
     "Прежняя версия: sol_backtest_v1.txt",
     f"Стартовая ликвидность пулов (base_sol): {sorted(set(round(v) for v in BASE_OF.values()))}",
     f"ИСТОРИЧЕСКИЙ ТЕСТ без заглядывания в будущее. Пулов с временем создания {len(order)} (без времени {len(missing)} — не использованы).",
     f"Первые {PRIME} пулов только строят список ботов. Тестируются пулы Семьи 1 после них: {len(test)}; ранний вывод (<40 с) у "
     f"{sum(1 for r in test if r['withdraw'] is not None and r['withdraw'] < 40)}.",
     f"Вход через {LAT} с после сигнала; расходы {COST * 100:.0f}% на сделку; цена ~ (SOL в пуле)^2; потеря при выводе ликвидности −100%.",
     "\nКОНТРОЛЬНЫЕ ТОЧКИ (медианы по пулам С1): ранний вывод против остальных"]
early = [r for r in test if r["withdraw"] is not None and r["withdraw"] < 40]
late = [r for r in test if not (r["withdraw"] is not None and r["withdraw"] < 40)]
md = lambda xs: round(st.median(xs), 2) if xs else "-"
for T in (15, 20, 25):
    L.append(f"  {T} с: боты N {md([r[f'N{T}'] for r in early])} / {md([r[f'N{T}'] for r in late])}; SOL ботов {md([r[f'sol{T}'] for r in early])} / {md([r[f'sol{T}'] for r in late])}; "
             f"новых за 5 с {md([r[f'new5_{T}'] for r in early])} / {md([r[f'new5_{T}'] for r in late])}; доля ядра {md([r[f'core{T}'] for r in early])} / {md([r[f'core{T}'] for r in late])}; "
             f"выведено к этому моменту {sum(r[f'wd_before_{T}'] for r in early)} из {len(early)}")


def block(rows, title):
    out = [f"\n{title} (пулов {len(rows)})"]
    out.append(f"  {'сигнал':<14}{'прошли':>7}{'избежали':>9}{'потерь':>7}" + "".join(f"{x:>10}" for x in ("+10с", "+20с", "до 60с", "цель5%", "цель10%", "цель15%")))
    for N, T in VARIANTS:
        sig = [r for r in rows if not r[f"wd_before_{T}"] and r[f"N{T}"] >= N]
        avoided = sum(1 for r in rows if r[f"wd_before_{T}"] or r[f"N{T}"] < N if r["withdraw"] is not None and r["withdraw"] < 40)
        t_in = T + LAT
        cols = []
        res_all = {}
        for name, fn in (("+10с", lambda p: ret(p, t_in, t_in + 10)), ("+20с", lambda p: ret(p, t_in, t_in + 20)), ("до 60с", lambda p: ret(p, t_in, 60)),
                         ("цель5%", lambda p: exit_target(p, t_in, 0.05)), ("цель10%", lambda p: exit_target(p, t_in, 0.10)), ("цель15%", lambda p: exit_target(p, t_in, 0.15))):
            rs = [x for x in (fn(r["pool"]) for r in sig) if x is not None]
            res_all[name] = rs
            cols.append(f"{st.mean(rs) * 100:+.1f}%" if rs else "-")
        losses = sum(1 for x in res_all["до 60с"] if x <= -0.99)
        out.append(f"  N>={N:<3} на {T} с{'':<2}{len(sig):>7}{avoided:>9}{losses:>7}" + "".join(f"{c:>10}" for c in cols))
    return out


L += block(test, "ВСЕ ТЕСТОВЫЕ ПУЛЫ С1 — средний итог на сделку после расходов (избежали = ранние выводы, отсеянные сигналом)")
half = len(test) // 2
L += block(test[:half], "ПЕРВАЯ ПОЛОВИНА ПО ВРЕМЕНИ")
L += block(test[half:], "ВТОРАЯ ПОЛОВИНА ПО ВРЕМЕНИ")
for c in FAM1:
    rs = [r for r in test if r["creator"] == c]
    if rs:
        L += block(rs, f"СОЗДАТЕЛЬ {c}")
L.append("\nОГОВОРКИ: 40 пулов — маленькая выборка; пулы одного создателя и одного парка не независимы; цена восстановлена по сумме SOL "
         "(без точных резервов монеты и без нашего влияния на цену); путь только до 60-й секунды.")
print("\n".join(L))
open(os.path.join(HERE, "sol_backtest.txt"), "w", encoding="utf-8").write("\n".join(L))
