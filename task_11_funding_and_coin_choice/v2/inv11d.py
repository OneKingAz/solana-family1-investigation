"""Task 11 v2.1 — final statistics (analyst's spec). No RPC. Reads investigation_task_11/v2/sessions_gap120.csv and pool_creator_fields.csv
(not changed). PRIMARY TEST (declared in this script before the run, but after earlier results had been seen — see the report):
  sample = PumpSwap sessions with the pool creator confirmed by the pool account field `creator`;
  last funder = the last direct SOL transfer >= 0.1 SOL into the nine before the session start;
  statistic = number of sessions where last funder == pool creator;
  null = the funder sequence keeps its shifts (maximal runs) but their order is permuted; ALL permutations are enumerated exactly.
All other variants are reported as secondary. Out (investigation_task_11/v2/): pool_creator_match_v21.csv, statistical_tests_v21.csv,
null_distributions_v21.csv."""
import collections, csv, itertools, json, math, os, random, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
V2 = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_11\v2"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
PF = {r["mint"]: r for r in rd(os.path.join(V2, "pool_creator_fields.csv"))}
SES = rd(os.path.join(V2, "sessions_gap120.csv"))
rows = []
for s in SES:
    p = PF.get(s["mint"], {})
    if p.get("program") == "PumpSwap" and p.get("pool_field_creator"):
        cr, q = p["pool_field_creator"], "pool_field_creator (подтверждён полем пула)"
    else:
        cr, q = s["pool_init_payer"], "pool_init_payer_unverified (Meteora, поле пула не декодировано)"
    rows.append(dict(mint=s["mint"], program=p.get("program", ""), pool_creator=cr, creator_quality=q, pool_init_payer=s["pool_init_payer"],
                     pool_field_creator=p.get("pool_field_creator", ""), session_start_utc=s["session_start_utc"], session_end_utc=s["session_end_utc"],
                     last_funder_ge01=s["last_funder_ge01"], last_funder_ge01_utc=s["last_funder_ge01_utc"], match_ge01=int(cr == s["last_funder_ge01"]) if cr and s["last_funder_ge01"] else "",
                     last_funder_any=s["last_funder_any"], match_any=int(cr == s["last_funder_any"]) if cr and s["last_funder_any"] else "",
                     note="торговля началась до первого пополнения: в тесты не входит" if not s["last_funder_ge01"] else ""))


def wcsv(name, rs):
    with open(os.path.join(V2, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rs)


wcsv("pool_creator_match_v21.csv", rows)


def runs(seq):
    out, cur = [], [seq[0]]
    for x in seq[1:]:
        if x == cur[-1]:
            cur.append(x)
        else:
            out.append(cur)
            cur = [x]
    out.append(cur)
    return out


random.seed(21)
tests, nulls = [], []
SAMPLES = (("S1: только PumpSwap, создатель подтверждён полем пула", lambda r: r["program"] == "PumpSwap" and r["creator_quality"].startswith("pool_field")),
           ("S2: PumpSwap + Meteora (Meteora = pool_init_payer_unverified)", lambda r: True))
for sname, flt in SAMPLES:
    for fkey, fname in (("ge01", "пополнение от 0.1 SOL"), ("any", "любое пополнение (с пылью)")):
        R = [r for r in rows if flt(r) and r[f"match_{fkey}"] != ""]
        cr = [r["pool_creator"] for r in R]
        fu = [r[f"last_funder_{fkey}"] for r in R]
        n, obs = len(R), sum(a == b for a, b in zip(cr, fu))
        bl = runs(fu)
        # 1) shift permutation: exact if feasible
        if math.factorial(len(bl)) <= 400000:
            perm = [sum(a == b for a, b in zip(cr, [x for i in o for x in bl[i]])) for o in itertools.permutations(range(len(bl)))]
            kind = f"точный перебор всех {len(perm)} перестановок"
        else:
            perm = []
            for _ in range(100000):
                o = list(range(len(bl)))
                random.shuffle(o)
                perm.append(sum(a == b for a, b in zip(cr, [x for i in o for x in bl[i]])))
            kind = f"{len(bl)}! слишком много — 100 000 случайных перестановок"
        circ = [sum(a == b for a, b in zip(cr, fu[k:] + fu[:k])) for k in range(n)]
        naive = []
        for _ in range(10000):
            f2 = fu[:]
            random.shuffle(f2)
            naive.append(sum(a == b for a, b in zip(cr, f2)))
        for tname, dist_, desc in (("перестановка смен", perm, kind), ("циклический сдвиг", circ, f"все {n} положений, включая исходное"),
                                    ("наивная перестановка сессий", naive, "10 000 случайных; считает сессии независимыми — неверно для смен, только для сравнения")):
            ge = sum(1 for x in dist_ if x >= obs)
            primary = sname.startswith("S1") and fkey == "ge01" and tname == "перестановка смен"
            tests.append(dict(primary=int(primary), sample=sname, funder=fname, test=tname, null_construction=desc, sessions=n, observed_matches=obs,
                              observed_share=round(obs / n, 4), funder_blocks=len(bl), block_lengths=" ".join(str(len(b)) for b in bl),
                              block_funders=" ".join(b[0][:8] for b in bl), null_size=len(dist_), null_mean=round(statistics.mean(dist_), 3),
                              null_ge_observed=ge, p_value=round(ge / len(dist_), 5)))
            nulls += [dict(sample=sname[:2], funder=fkey, test=tname, i=i, matches=x) for i, x in enumerate(dist_)]
wcsv("statistical_tests_v21.csv", tests)
wcsv("null_distributions_v21.csv", nulls)
for t in tests:
    print(("ОСНОВНОЙ " if t["primary"] else "         ") + f"{t['sample'][:3]} {t['funder'][:14]:14} {t['test']:28} n={t['sessions']} совп={t['observed_matches']} "
          f"блоков={t['funder_blocks']} ({t['block_lengths'][:40]}) среднее H0={t['null_mean']} p={t['p_value']}")
