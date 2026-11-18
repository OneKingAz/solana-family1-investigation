"""Task 02 (analyst, 18.11): dual roles and anomalous wallets around GEKKO / family 1. NO RPC; source files and earlier results are only read.
Sources: sol_buyers.csv (v2 roles; swaps of the first 60 s of 40 pools 18.11, seconds from creation, no signatures), sol_pool_rec.jsonl /
sol_watch_paths.jsonl (pool creation times + creator from the pool's data), sol_pools.csv (69 pools of 7 creators, 17.11, CreatePool by the
creator's own transactions), sol_watch_creators.json, sol_export_transfers.csv / sol_export_trades.csv (17.11, signatures and slots),
sol_insiders_trades.csv (17.11, the «own» tag), investigation_task_01/bot_creator_overlap.csv.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_02\\ (dual_roles.csv, wallet_timeline.csv, creator_park_intersections.csv,
fund_flow_validation.csv, _facts.json). Times: ISO 8601 UTC."""
import collections, csv, datetime as dt, json, os, statistics as st, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_02"
os.makedirs(OUT, exist_ok=True)
TRE, SPO, GC = "B7StC42h126Hmtkw4GoRMcaHA5ZuKawfa9fCSTV6UMSj", "3azG8rmtPnNUz77a6UqBKt1ykpk3JQpLLNTaoXW31b34", "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
X7 = "7hm4V7g2hfdmhaA2c6KLnnAoYsp8CvY8B5xYhCbNjppR"
INFRA = {TRE: "казна", SPO: "спонсор", GC: "создатель GEKKO"}
iso = lambda u: dt.datetime.fromtimestamp(float(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if u not in (None, "") else ""
rd = lambda fn: list(csv.DictReader(open(os.path.join(A, fn), encoding="utf-8-sig"), delimiter=";"))

buys = rd("sol_buyers.csv")
PARK = {r["who"] for r in buys if r["role"] == "парк"}
# ---- every known pool creator and the evidence of it ----
CREATORS = collections.defaultdict(list)  # wallet -> [(pool, created_unix, source)]
created = {}
for fn, key, shift in (("sol_pool_rec.jsonl", "created", 0), ("sol_watch_paths.jsonl", "t0", -1)):
    for l in open(os.path.join(A, fn), encoding="utf-8"):
        d = json.loads(l)
        tc = float(d[key]) + shift if d.get(key) else None
        created.setdefault(d["pool"], tc)
        if d.get("creator"):
            CREATORS[d["creator"]].append((d["pool"], tc, fn + (": поле creator = данные пула, смещение 11" if fn == "sol_pool_rec.jsonl" else ": создатель, чья транзакция CreatePool пойманa")))
for r in rd("sol_pools.csv"):
    CREATORS[r["creator"]].append((r["pool"], None, "sol_pools.csv 17.11: CreatePool в транзакциях самого создателя (" + r["created"] + " по часам ПК)"))
try:
    for w in json.load(open(os.path.join(A, "sol_watch_creators.json"), encoding="utf-8")):
        CREATORS.setdefault(w, [])
except OSError:
    pass
pool_creator = {}
for r in buys:
    if r["creator"]:
        pool_creator[r["pool"]] = r["creator"]
        if r["pool"] not in [p for p, _, _ in CREATORS[r["creator"]]]:
            CREATORS[r["creator"]].append((r["pool"], created.get(r["pool"]), "sol_buyers.csv: поле creator"))

T = rd("sol_export_transfers.csv")
TR17 = rd("sol_export_trades.csv")
INS = rd("sol_insiders_trades.csv")
own_tag = {}
for r in INS:
    if r.get("own"):
        own_tag[r["wallet"]] = r["own"]
EXP_WIN = (min(int(r["blockTime"]) for r in T), max(int(r["blockTime"]) for r in T))
sol_tr = [r for r in T if r["asset"] == "SOL" and r["in_trade"] != "True"]

# ---------- per wallet facts ----------
def facts(w):
    f = dict(wallet=w)
    f["creator_pools"] = len(CREATORS.get(w, []))
    f["creator_sources"] = "; ".join(sorted({s.split(":")[0] for _, _, s in CREATORS.get(w, [])}))
    my = [r for r in buys if r["who"] == w and r["kind"] == "buy"]
    f["pools_18"] = len({r["pool"] for r in my})
    f["buys_18"] = len(my)
    f["own_pool_buys_18"] = sum(1 for r in my if pool_creator.get(r["pool"]) == w)
    f["other_pool_buys_18"] = sum(1 for r in my if pool_creator.get(r["pool"]) not in (w, None))
    f["median_buy_second_18"] = round(st.median(float(r["t"]) for r in my), 1) if my else ""
    f["median_buy_sol_18"] = round(st.median(float(r["sol"]) for r in my), 3) if my else ""
    gin = [r for r in sol_tr if r["destination"] == w and r["source"] in INFRA]
    gout = [r for r in sol_tr if r["source"] == w and r["destination"] in INFRA]
    f["sol_from_infra_17"] = round(sum(float(r["amount"]) for r in gin), 4)
    f["n_from_infra_17"] = len(gin)
    f["sol_to_infra_17"] = round(sum(float(r["amount"]) for r in gout), 4)
    f["n_to_infra_17"] = len(gout)
    f["from_which"] = "+".join(sorted({INFRA[r["source"]] for r in gin}))
    f["to_which"] = "+".join(sorted({INFRA[r["destination"]] for r in gout}))
    f["tag_17_11"] = own_tag.get(w, "")
    f["in_export_17"] = int(any(r["wallet"] == w for r in TR17) or any(r["source"] == w or r["destination"] == w for r in T))
    f["park"] = int(w in PARK)
    f["infra"] = INFRA.get(w, "")
    return f


cand = set(PARK) | set(CREATORS) | set(INFRA)
F = {w: facts(w) for w in cand}

# ---------- creator_park_intersections.csv ----------
with open(os.path.join(OUT, "creator_park_intersections.csv"), "w", newline="", encoding="utf-8-sig") as fo:
    keys = ["wallet", "park", "infra", "creator_pools", "creator_sources", "pools_18", "own_pool_buys_18", "other_pool_buys_18", "sol_from_infra_17", "sol_to_infra_17", "tag_17_11"]
    wtr = csv.DictWriter(fo, fieldnames=keys, delimiter=";", extrasaction="ignore")
    wtr.writeheader()
    for w in sorted(cand, key=lambda w: (-F[w]["park"], -F[w]["creator_pools"], w)):
        if F[w]["park"] or F[w]["creator_pools"] or F[w]["infra"]:
            wtr.writerow(F[w])

# ---------- dual_roles.csv ----------
ROLES = [("создатель пула", lambda f: f["creator_pools"] > 0), ("парк", lambda f: f["park"] == 1), ("спонсор/казна/создатель GEKKO", lambda f: bool(f["infra"])),
         ("получал SOL от инфраструктуры (17.11)", lambda f: f["sol_from_infra_17"] > 0), ("отправлял SOL инфраструктуре (17.11)", lambda f: f["sol_to_infra_17"] > 0),
         ("покупал в чужих пулах (18.11)", lambda f: f["other_pool_buys_18"] > 0)]
dual = []
for w, f in F.items():
    rs = [name for name, fn in ROLES if fn(f)]
    if len(rs) >= 2:
        dual.append(dict(wallet=w, roles_n=len(rs), roles=" | ".join(rs), **{k: f[k] for k in ("creator_pools", "creator_sources", "pools_18", "own_pool_buys_18",
                                                                                              "other_pool_buys_18", "n_from_infra_17", "sol_from_infra_17", "from_which",
                                                                                              "n_to_infra_17", "sol_to_infra_17", "to_which", "tag_17_11")}))
dual.sort(key=lambda r: (-r["roles_n"], -r["sol_to_infra_17"]))
with open(os.path.join(OUT, "dual_roles.csv"), "w", newline="", encoding="utf-8-sig") as fo:
    wtr = csv.DictWriter(fo, fieldnames=list(dual[0].keys()), delimiter=";")
    wtr.writeheader()
    wtr.writerows(dual)
combo = collections.Counter(r["roles"] for r in dual)

# ---------- wallet_timeline.csv: 7hm4 + creators that are also park / funded + the 10 park wallets with the largest returns to the infra ----------
susp = [X7] + [r["wallet"] for r in dual if "создатель пула" in r["roles"] and r["wallet"] != X7]
susp += [r["wallet"] for r in sorted(dual, key=lambda r: -r["sol_to_infra_17"]) if "парк" in r["roles"] and r["wallet"] not in susp][:10]
susp += [SPO]
TL = []
for w in dict.fromkeys(susp):
    for r in T:
        if r["asset"] == "SOL" and r["in_trade"] != "True" and (r["source"] == w or r["destination"] == w) and ({r["source"], r["destination"]} & set(INFRA) or w == X7):
            other = r["destination"] if r["source"] == w else r["source"]
            TL.append(dict(wallet=w, time_utc=iso(r["blockTime"]), unix=r["blockTime"], slot=r["slot"], event="получил SOL" if r["destination"] == w else "отправил SOL",
                           counterparty=other, counterparty_role=INFRA.get(other, "парк" if other in PARK else ""), sol=r["amount"], signature=r["signature"],
                           precision="слот, подпись", source="sol_export_transfers.csv"))
    tr = [r for r in TR17 if r["wallet"] == w]
    if tr:
        r = min(tr, key=lambda r: int(r["slot"]))
        TL.append(dict(wallet=w, time_utc=iso(r["blockTime"]), unix=r["blockTime"], slot=r["slot"], event=f"первая сделка в выгрузке 17.11 ({r['side']})", counterparty=r["pool"],
                       counterparty_role="пул", sol=r["solAmount"], signature=r["signature"], precision="слот, подпись", source="sol_export_trades.csv"))
    for p, tc, src in CREATORS.get(w, []):
        TL.append(dict(wallet=w, time_utc=iso(tc) if tc else "", unix=tc or "", slot="", event="создание пула", counterparty=p, counterparty_role="свой пул",
                       sol="", signature="", precision="время блока/наблюдения, без подписи", source=src.split(":")[0]))
    for r in [r for r in buys if r["who"] == w and r["kind"] == "buy"]:
        tc = created.get(r["pool"])
        u = tc + float(r["t"]) if tc else None
        TL.append(dict(wallet=w, time_utc=iso(u) if u else "", unix=round(u) if u else "", slot="", event="покупка в " + ("своём" if pool_creator.get(r["pool"]) == w else "чужом") + " пуле",
                       counterparty=r["pool"], counterparty_role="создатель " + (pool_creator.get(r["pool"]) or "")[:8], sol=r["sol"], signature="",
                       precision="±1 с (секунды от создания пула), без подписи", source="sol_buyers.csv"))
TL.sort(key=lambda r: (r["wallet"], float(r["unix"] or 0)))
with open(os.path.join(OUT, "wallet_timeline.csv"), "w", newline="", encoding="utf-8-sig") as fo:
    wtr = csv.DictWriter(fo, fieldnames=list(TL[0].keys()), delimiter=";")
    wtr.writeheader()
    wtr.writerows(TL)

# ---------- fund_flow_validation.csv ----------
FF = []
for a, b in ((TRE, SPO), (SPO, GC), (GC, TRE)):
    xs = sorted((r for r in sol_tr if r["source"] == a and r["destination"] == b), key=lambda r: int(r["slot"]))
    for r in xs:
        FF.append(dict(leg=f"{INFRA[a]} → {INFRA[b]}", signature=r["signature"], slot=r["slot"], time_utc=iso(r["blockTime"]), unix=r["blockTime"], sol=r["amount"]))
with open(os.path.join(OUT, "fund_flow_validation.csv"), "w", newline="", encoding="utf-8-sig") as fo:
    wtr = csv.DictWriter(fo, fieldnames=list(FF[0].keys()), delimiter=";")
    wtr.writeheader()
    wtr.writerows(FF)
# flows of each infra address within the export (in / out, by counterparty kind)
flow = {}
for w in INFRA:
    ins_ = [r for r in sol_tr if r["destination"] == w]
    outs = [r for r in sol_tr if r["source"] == w]
    kind = lambda o: INFRA.get(o, "парк" if o in PARK else "прочие")
    fin = collections.Counter()
    fout = collections.Counter()
    for r in ins_:
        fin[kind(r["source"])] += float(r["amount"])
    for r in outs:
        fout[kind(r["destination"])] += float(r["amount"])
    flow[INFRA[w]] = dict(in_total=round(sum(fin.values()), 2), out_total=round(sum(fout.values()), 2), in_by={k: round(v, 2) for k, v in fin.items()},
                          out_by={k: round(v, 2) for k, v in fout.items()}, n_in=len(ins_), n_out=len(outs))
# ordering: for each GEKKO creator -> treasury transfer, the latest sponsor -> creator transfer before it and the creator's inflows in between
legs = {k: sorted(((int(r["slot"]), float(r["amount"]), r["signature"], int(r["blockTime"])) for r in sol_tr if r["source"] == a and r["destination"] == b))
        for k, (a, b) in {"tre_spo": (TRE, SPO), "spo_gc": (SPO, GC), "gc_tre": (GC, TRE)}.items()}
order = []
for s, amt, sig, bt in legs["gc_tre"]:
    prev = [x for x in legs["spo_gc"] if x[0] < s]
    p = prev[-1] if prev else None
    other_in = sum(float(r["amount"]) for r in sol_tr if r["destination"] == GC and r["source"] != SPO and p and p[0] < int(r["slot"]) < s)
    order.append(dict(gc_to_treasury_sig=sig, slot=s, time=iso(bt), sol=amt, prev_sponsor_to_gc_sig=p[2] if p else "", prev_slot=p[0] if p else "",
                      prev_sol=p[1] if p else "", minutes_between=round((bt - p[3]) / 60, 1) if p else "", other_inflow_to_gc_between=round(other_in, 2)))
json.dump(dict(F_X7=F.get(X7), creators_of_X7=CREATORS.get(X7, []), dual_n=len(dual), combos=combo.most_common(), park_creators=[w for w in PARK if CREATORS.get(w)],
               flow=flow, legs={k: (len(v), round(sum(x[1] for x in v), 2), iso(v[0][3]) if v else "", iso(v[-1][3]) if v else "") for k, v in legs.items()},
               order=order, export_window=(iso(EXP_WIN[0]), iso(EXP_WIN[1])),
               x7_vs_park=dict(x7_sec=F[X7]["median_buy_second_18"], x7_sol=F[X7]["median_buy_sol_18"],
                               park_sec=st.median(F[w]["median_buy_second_18"] for w in PARK if F[w]["median_buy_second_18"] != ""),
                               park_sol=st.median(F[w]["median_buy_sol_18"] for w in PARK if F[w]["median_buy_sol_18"] != "")),
               tag_counts=collections.Counter(own_tag.get(w, "нет тега") for w in PARK)),
          open(os.path.join(OUT, "_facts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(open(os.path.join(OUT, "_facts.json"), encoding="utf-8").read()[:6000])
