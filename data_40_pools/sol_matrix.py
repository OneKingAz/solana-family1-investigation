"""18.11 (user + analyst: «идентификация инфраструктуры, повторно участвующей в запусках»). A matrix of all pools of sol_buyers.csv
(first 60 s of every pool, every swap) + the pool paths (sol_pool_rec.jsonl / sol_watch_paths.jsonl, 10-15 min) — no new node requests.
Per pool: creator, family, the creator's own first buy, buys / buyers / SOL in by 10-20-30-60 s, the pump bots (wallets in 3+ pools) present,
when the first pump bot came, max pool SOL in the path, withdraw time and pool SOL at the withdraw.
Then: (1) the creator 6e7XUsDb — its early-withdraw pools against its other pools, feature by feature;
(2) GLEBhVYd against the rest of family 1; (3) the infrastructure: which pump bots work for which families (bot x family table),
and how similar the bot sets of two pools are (Jaccard), inside a family and between families.
Out: analysis/sol_matrix.csv, analysis/sol_matrix.txt.  Usage: python sol_matrix.py"""
import collections, csv, json, os, statistics as st, sys

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
FAM = {  # by the creator's own first buy (sol_razbor 18.11)
    "6e7XUsDb": 1, "6yf7adkH": 1, "29iqxoNv": 1, "CPC8iEE1": 1, "GLEBhVYd": 1, "8vB8UUGx": 1,
    "3Uy8Rjje": 2, "26bWsjWy": 2, "EQQeRyoM": 2, "FCAVx5kZ": 2,
    "FccvQaNh": 3, "EFTXEqsx": 3, "DbCtLeG4": 4, "DxVhPq9Y": 4,
}
ev = collections.defaultdict(list)
creator = {}
for r in csv.DictReader(open(os.path.join(HERE, "sol_buyers.csv"), encoding="utf-8-sig"), delimiter=";"):
    ev[r["pool"]].append(r)
    creator[r["pool"]] = r["creator"] or ""
paths = {}
for fn in ("sol_pool_rec.jsonl", "sol_watch_paths.jsonl"):
    try:
        for l in open(os.path.join(HERE, fn), encoding="utf-8"):
            d = json.loads(l)
            paths.setdefault(d["pool"], d)
            if d.get("creator"):
                creator.setdefault(d["pool"], d["creator"])
    except OSError:
        pass
# pump bots = wallets that bought >= 0.05 SOL in 3+ pools (the dust markers buy ~0)
pools_of = collections.defaultdict(set)
for p, es in ev.items():
    for e in es:
        if e["kind"] == "buy" and float(e["sol"]) >= 0.05 and e["who"] != creator.get(p):
            pools_of[e["who"]].add(p)
PUMP = {w for w, ps in pools_of.items() if len(ps) >= 3}
# v2 (analyst 18.11): one definition in all scripts (sol_roles.py): «парк» = >= 0.05 SOL in 3+ pools; «пыль-маркер» = buys in 3+ pools
# and never more than 0.001 SOL; v1 put ANY wallet with one buy < 0.001 SOL into DUST (1998 wallets)
any_pools, max_buy = collections.defaultdict(set), collections.defaultdict(float)
for p, es in ev.items():
    for e in es:
        if e["kind"] == "buy" and e["who"] != creator.get(p):
            any_pools[e["who"]].add(p)
            max_buy[e["who"]] = max(max_buy[e["who"]], float(e["sol"]))
DUST = {w for w, ps in any_pools.items() if len(ps) >= 3 and max_buy[w] < 0.001}
SMALL3 = {w for w, ps in any_pools.items() if len(ps) >= 3 and w not in PUMP and w not in DUST}  # repeat, small, not the pump


def path_withdraw(d):
    """(withdraw second from the pool's creation, pool SOL before it, max SOL) from a recorded path"""
    if not d or not d.get("path"):
        return None, None, None
    path = d["path"]
    if "created" in d:  # sol_pool_rec: t from creation
        pts = [(x[0], x[1]) for x in path]
    else:  # sol_watch: t from our detection (~1 s after creation)
        pts = [(x[0] + 1.0, x[1]) for x in path]
    mx = max(s for _, s in pts)
    for (t0, s0), (t1, s1) in zip(pts, pts[1:]):
        if s0 > 5 and s1 < 0.2 * s0:
            return round(t1, 1), round(s0, 1), round(mx, 1)
    return None, None, round(mx, 1)


rows = []
for p, es in ev.items():
    cr = creator.get(p, "")
    c8 = cr[:8]
    buys = [e for e in es if e["kind"] == "buy"]
    sells = [e for e in es if e["kind"] == "sell"]
    t = lambda e: float(e["t"])
    first = next((e for e in buys if e["who"] == cr), None)
    own = float(first["sol"]) if first else 0.0
    pump = [e for e in buys if e["who"] in PUMP]
    outs = [e for e in buys if e["who"] not in PUMP and e["who"] not in DUST and e["who"] != cr]
    wd60 = next((float(e["withdraw_s"]) for e in es if e["withdraw_s"] not in ("", "None")), None)
    wd_path, wd_sol, mx = path_withdraw(paths.get(p))
    wd = wd60 if wd60 is not None else wd_path
    row = dict(pool=p, creator=cr, family=FAM.get(c8, 0), own_buy=round(own, 2),
               withdraw_s=wd, withdraw_pool_sol=wd_sol, max_pool_sol=mx, early=int(wd is not None and wd < 40))
    for lim in (10, 20, 30, 60):
        b = [e for e in buys if t(e) < lim and e["who"] != cr]
        row[f"buys_{lim}"] = len(b)
        row[f"sol_in_{lim}"] = round(sum(float(e["sol"]) for e in b), 2)
    row["buyers_60"] = len({e["who"] for e in buys})
    row["sells_60"] = len(sells)
    row["sol_out_60"] = round(-sum(float(e["sol"]) for e in sells), 2)
    row["pump_bots"] = len({e["who"] for e in pump})
    row["pump_buys"] = len(pump)
    row["pump_sol"] = round(sum(float(e["sol"]) for e in pump), 2)
    row["first_pump_s"] = min((t(e) for e in pump), default=None)
    row["outsider_buys"] = len(outs)
    row["outsider_sol"] = round(sum(float(e["sol"]) for e in outs), 2)
    row["big_outsider_sol"] = round(max((float(e["sol"]) for e in outs), default=0), 2)
    row["dust_bots"] = len({e["who"] for e in buys if e["who"] in DUST})
    row["_bots"] = {e["who"] for e in pump}
    rows.append(row)

keys = [k for k in rows[0] if not k.startswith("_")]
with open(os.path.join(HERE, "sol_matrix.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=keys, delimiter=";", extrasaction="ignore")
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: (r["family"], r["creator"])))

med = lambda xs: round(st.median(xs), 2) if xs else "-"
FEAT = ["own_buy", "buys_10", "buys_20", "buys_30", "buys_60", "sol_in_10", "sol_in_30", "sol_in_60", "buyers_60", "sells_60", "sol_out_60",
        "pump_bots", "pump_buys", "pump_sol", "first_pump_s", "outsider_buys", "outsider_sol", "big_outsider_sol", "dust_bots", "max_pool_sol"]


def compare(title, a, b, na, nb):
    L = [f"\n{title}: {na} — {len(a)} пулов, {nb} — {len(b)} пулов (медианы)"]
    L.append(f"  {'признак':<18}{na[:22]:>24}{nb[:22]:>24}")
    for k in FEAT:
        va = [r[k] for r in a if r[k] is not None]
        vb = [r[k] for r in b if r[k] is not None]
        L.append(f"  {k:<18}{str(med(va)):>24}{str(med(vb)):>24}")
    return L


L = ["ВЕРСИЯ 2 (18.11, по замечаниям аналитика): единые роли кошельков, Жаккар по всем парам между семьями. Прежняя: sol_matrix_v1.txt",
     f"МАТРИЦА ПУЛОВ SOLANA: {len(rows)} пулов. Роли кошельков (покупали в 3+ пулах): парк (покупка >= 0.05 SOL) {len(PUMP)}, "
     f"пыль-маркеры (все покупки < 0.001 SOL) {len(DUST)}, прочие повторяющиеся мелкие {len(SMALL3)}; всего повторяющихся {len(PUMP) + len(DUST) + len(SMALL3)}"]
fam_of_pool = {}
for r in rows:
    fam_of_pool[r["pool"]] = r["family"]
L.append(f"  кошельков парка, покупавших в пулах больше чем одной семьи: {sum(1 for w in PUMP if len({fam_of_pool.get(q) for q in pools_of[w]}) > 1)}")
L.append("Полная матрица: analysis/sol_matrix.csv (строка = пул, столбцы = признаки)")
L.append("\nПО СЕМЬЯМ (медианы):")
L.append(f"  {'семья':<7}{'пулов':>6}{'ранний вывод':>14}{'своя покупка':>14}{'боты накачки':>14}{'покупок 60с':>12}{'SOL 60с':>9}{'1-й бот, с':>11}{'макс пул':>10}")
for fam in sorted({r["family"] for r in rows}):
    rs = [r for r in rows if r["family"] == fam]
    L.append(f"  {fam if fam else 'прочие':<7}{len(rs):>6}{sum(r['early'] for r in rs):>14}{med([r['own_buy'] for r in rs]):>14}{med([r['pump_bots'] for r in rs]):>14}"
             f"{med([r['buys_60'] for r in rs]):>12}{med([r['sol_in_60'] for r in rs]):>9}{med([r['first_pump_s'] for r in rs if r['first_pump_s'] is not None]):>11}"
             f"{med([r['max_pool_sol'] for r in rs if r['max_pool_sol']]):>10}")

six = [r for r in rows if r["creator"].startswith("6e7XUsDb")]
L += compare("1) СОЗДАТЕЛЬ 6e7XUsDb: ранний вывод против остальных его пулов", [r for r in six if r["early"]], [r for r in six if not r["early"]], "ранний вывод", "без раннего")
L.append("  по пулам:")
for r in sorted(six, key=lambda r: str(r["withdraw_s"])):
    L.append(f"    {r['pool'][:8]} вывод {r['withdraw_s']} с при {r['withdraw_pool_sol']} SOL, макс {r['max_pool_sol']}; покупок 10/30/60 с: {r['buys_10']}/{r['buys_30']}/{r['buys_60']}; "
             f"ботов накачки {r['pump_bots']}, 1-й на {r['first_pump_s']} с; посторонние {r['outsider_buys']} покупок на {r['outsider_sol']} SOL (крупнейшая {r['big_outsider_sol']})")
fam1 = [r for r in rows if r["family"] == 1]
L += compare("2) GLEBhVYd ПРОТИВ ОСТАЛЬНОЙ СЕМЬИ 1", [r for r in fam1 if r["creator"].startswith("GLEBhVYd")],
             [r for r in fam1 if not r["creator"].startswith("GLEBhVYd")], "GLEBhVYd", "остальные С1")
L += compare("3) ВСЕ РАННИЕ ВЫВОДЫ ПРОТИВ ВСЕХ ОСТАЛЬНЫХ", [r for r in rows if r["early"]], [r for r in rows if not r["early"]], "ранний вывод", "без раннего")

L.append("\n4) ИНФРАСТРУКТУРА: боты накачки × семьи (в скольких пулах семьи бот покупал)")
fams = sorted({r["family"] for r in rows})
fam_n = {f: sum(1 for r in rows if r["family"] == f) for f in fams}
L.append("  " + f"{'бот':<10}" + "".join(f"{('С' + str(f)) if f else 'проч':>7}" for f in fams) + "  (пулов в семье: " + ", ".join(f"{('С' + str(f)) if f else 'проч'}={fam_n[f]}" for f in fams) + ")")
for wlt in sorted(PUMP, key=lambda w: -len(pools_of[w]))[:30]:
    cnt = collections.Counter(next(r["family"] for r in rows if r["pool"] == p) for p in pools_of[wlt])
    L.append("  " + f"{wlt[:8]:<10}" + "".join(f"{cnt.get(f, 0):>7}" for f in fams))
L.append("\n5) ПОХОЖЕСТЬ НАБОРА БОТОВ (Жаккар, медиана по парам пулов)")
def jac(a, b):
    return len(a & b) / len(a | b) if a | b else None
for fa in fams:
    for fb in fams:
        if fb < fa:
            continue
        # v2 (analyst 18.11): x < y only inside one family; between two families every pair (v1 dropped some by the address order)
        v = [jac(x["_bots"], y["_bots"]) for x in rows for y in rows if x["family"] == fa and y["family"] == fb and (fa != fb or x["pool"] < y["pool"])]
        v = [x for x in v if x is not None]
        if v:
            L.append(f"  {('С' + str(fa)) if fa else 'проч'} – {('С' + str(fb)) if fb else 'проч'}: {med(v)} (пар {len(v)})")
print("\n".join(L))
open(os.path.join(HERE, "sol_matrix.txt"), "w", encoding="utf-8").write("\n".join(L))
