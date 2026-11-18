"""Task 01 (analyst, 18.11): funding structure of the Solana pool creators 6e7XUsDb and GLEBhVYd, their intermediaries and the 170 wallets
of the family-1 pump fleet. NO new RPC requests, source files are only read. Sources:
  sol_buyers.csv (v2 roles)            — swaps of the first 60 s of 40 pools of 18.11 (no signatures/slots: only seconds from creation)
  sol_pool_rec.jsonl / sol_watch_paths — pool creation times
  sol_export_transfers.csv             — 17.11 GEKKO export: every SOL / token transfer of 112 farm wallets + creator Czg8kh3E + sponsor
                                         3azG8rmt (signature, blockTime, slot, source, destination, amount)
  sol_export_raw.jsonl.gz              — the same export, raw transactions (searched for any mention of the two creators)
  sol_export_trades.csv                — 17.11 swaps of those wallets (group = how the wallet was classified then)
  sol_watch.log, sol_trader.log        — moments when our watchers saw a >= 20 SOL plain transfer between a wallet and the treasury/sponsor
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_01\\ (funding_graph.csv, funding_transactions.csv, creator_connections.csv,
bot_creator_overlap.csv, investigation_report.md). Times: ISO 8601 UTC (+ unix seconds where known)."""
import collections, csv, datetime as dt, gzip, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_01"
os.makedirs(OUT, exist_ok=True)
TREASURY, SPONSOR = "B7StC42h126Hmtkw4GoRMcaHA5ZuKawfa9fCSTV6UMSj", "3azG8rmtPnNUz77a6UqBKt1ykpk3JQpLLNTaoXW31b34"
GEKKO_CREATOR_PREFIX = "Czg8kh3E"
iso = lambda u: dt.datetime.fromtimestamp(float(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if u not in (None, "") else ""

# ---- 18.11 pools, roles, creators ----
buys = list(csv.DictReader(open(os.path.join(A, "sol_buyers.csv"), encoding="utf-8-sig"), delimiter=";"))
created = {}
for fn, key, shift in (("sol_pool_rec.jsonl", "created", 0), ("sol_watch_paths.jsonl", "t0", -1)):
    for l in open(os.path.join(A, fn), encoding="utf-8"):
        d = json.loads(l)
        if d.get(key):
            created.setdefault(d["pool"], float(d[key]) + shift)
full = {}
for r in buys:
    if r["creator"]:
        full[r["creator"][:8]] = r["creator"]
C6, CG = full["6e7XUsDb"], full["GLEBhVYd"]
TARGETS = {"6e7XUsDb": C6, "GLEBhVYd": CG}
FAM1 = {k: full[k] for k in ("6e7XUsDb", "6yf7adkH", "29iqxoNv", "CPC8iEE1", "GLEBhVYd", "8vB8UUGx") if k in full}
PARK = {r["who"] for r in buys if r["role"] == "парк"}
pools_of = collections.defaultdict(list)
for r in buys:
    if r["kind"] == "buy" and r["who"] == r["creator"]:
        pools_of[r["creator"]].append((r["pool"], float(r["t"]), float(r["sol"])))
pool_creator = {r["pool"]: r["creator"] for r in buys}

# ---- 17.11 export ----
transfers = list(csv.DictReader(open(os.path.join(A, "sol_export_transfers.csv"), encoding="utf-8-sig"), delimiter=";"))
trades17 = list(csv.DictReader(open(os.path.join(A, "sol_export_trades.csv"), encoding="utf-8-sig"), delimiter=";"))
group17 = {}
for r in trades17:
    group17.setdefault(r["wallet"], r["group"])
gekko_creator = next((w for w in {r["source"] for r in transfers} | {r["destination"] for r in transfers} if w.startswith(GEKKO_CREATOR_PREFIX)), None)
INFRA = {TREASURY: "казна", SPONSOR: "спонсор"}
if gekko_creator:
    INFRA[gekko_creator] = "создатель GEKKO 17.11"
t_lo = min(int(r["blockTime"]) for r in transfers)
t_hi = max(int(r["blockTime"]) for r in transfers)

# raw transactions: any mention of the two creators or of the other family-1 creators
raw_hits = []
with gzip.open(os.path.join(A, "sol_export_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        hit = [k for k, v in FAM1.items() if v in line]
        if hit:
            try:
                t = json.loads(line)
            except ValueError:
                continue
            raw_hits.append((hit, t))

# ---- logs: >= 20 SOL plain transfers with the treasury/sponsor seen live (direction NOT recorded by the log) ----
log_events = []
for fn in ("sol_watch.log", "sol_trader.log"):
    for l in open(os.path.join(A, fn), encoding="utf-8", errors="replace"):
        m = re.match(r"(\d\d)\.(\d\d) (\d\d:\d\d:\d\d) (?:НОВЫЙ СОЗДАТЕЛЬ\? |новый создатель )(\w+)(.*)", l)
        if m:
            d, mo, hms, w, rest = m.groups()
            local = dt.datetime.strptime(f"2026-{mo}-{d} {hms}", "%Y-%m-%d %H:%M:%S")
            u = (local - dt.timedelta(hours=6)).replace(tzinfo=dt.timezone.utc).timestamp()  # the PC clock is UTC+6
            log_events.append(dict(wallet=w, unix=u, iso=iso(u), source=fn, text=(w + rest).strip()[:120]))

# ---------- funding_transactions.csv ----------
FT = []
for r in transfers:
    s, d = r["source"], r["destination"]
    tag = None
    if s in TARGETS.values() or d in TARGETS.values():
        tag = "создатель 6e7X/GLEB"
    elif (s in PARK or d in PARK) and r["asset"] == "SOL" and r["in_trade"] != "True" and ({s, d} & set(INFRA)):
        tag = "кошелёк парка 18.11 ↔ инфраструктура С1"
    elif s in INFRA and d in INFRA:
        tag = "инфраструктура"
    if tag:
        FT.append(dict(signature=r["signature"], slot=r["slot"], unix=r["blockTime"], time_utc=iso(r["blockTime"]), asset=r["asset"],
                       source=s, source_role=INFRA.get(s) or ("парк" if s in PARK else r["source_role"]),
                       destination=d, destination_role=INFRA.get(d) or ("парк" if d in PARK else r["destination_role"]),
                       amount=r["amount"], in_trade=r["in_trade"], why=tag, data_source="sol_export_transfers.csv (17.11)"))
for e in log_events:
    if e["wallet"][:8] in FAM1 or any(e["wallet"] == v for v in FAM1.values()):
        FT.append(dict(signature="", slot="", unix=round(e["unix"]), time_utc=e["iso"], asset="SOL", source="(в журнале не записано)", source_role="",
                       destination=e["wallet"], destination_role="создатель С1", amount="≥20 (35 по тексту журнала)" if "35" in e["text"] else "≥20",
                       in_trade="", why="перевод с казной/спонсором (направление не записано)", data_source=e["source"]))
FT.sort(key=lambda x: float(x["unix"] or 0))
with open(os.path.join(OUT, "funding_transactions.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(FT[0].keys()) if FT else ["signature"], delimiter=";")
    w.writeheader()
    w.writerows(FT)

# ---------- funding_graph.csv (aggregated SOL edges touching the park, the infra, the two creators) ----------
edges = collections.defaultdict(lambda: [0.0, 0, None, None])
for r in transfers:
    if r["asset"] != "SOL" or r["in_trade"] == "True":
        continue
    s, d = r["source"], r["destination"]
    if not ({s, d} & (PARK | set(INFRA) | set(TARGETS.values()))):
        continue
    e = edges[(s, d)]
    e[0] += float(r["amount"])
    e[1] += 1
    t = int(r["blockTime"])
    e[2] = t if e[2] is None else min(e[2], t)
    e[3] = t if e[3] is None else max(e[3], t)
role = lambda w: INFRA.get(w) or ("парк 18.11" if w in PARK else ("создатель " + w[:8] if w in TARGETS.values() else group17.get(w, "")))
with open(os.path.join(OUT, "funding_graph.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["source", "source_role", "destination", "destination_role", "sol_total", "transfers", "first_utc", "last_utc"])
    for (s, d), (amt, n, a, b) in sorted(edges.items(), key=lambda kv: -kv[1][0]):
        w.writerow([s, role(s), d, role(d), round(amt, 6), n, iso(a), iso(b)])

# ---------- bot_creator_overlap.csv: each park wallet against the 17.11 funding infrastructure and the 18.11 creators ----------
park_rows = []
for p in sorted(PARK):
    got = [r for r in transfers if r["destination"] == p and r["asset"] == "SOL" and r["in_trade"] != "True"]
    sent = [r for r in transfers if r["source"] == p and r["asset"] == "SOL" and r["in_trade"] != "True"]
    from_infra = collections.Counter()
    for r in got:
        if r["source"] in INFRA:
            from_infra[INFRA[r["source"]]] += float(r["amount"])
    to_infra = collections.Counter()
    for r in sent:
        if r["destination"] in INFRA:
            to_infra[INFRA[r["destination"]]] += float(r["amount"])
    pools18 = {r["pool"] for r in buys if r["who"] == p and r["kind"] == "buy"}
    park_rows.append(dict(wallet=p, group_17_11=group17.get(p, "нет в выгрузке 17.11"),
                          sol_from_gekko_creator=round(from_infra.get("создатель GEKKO 17.11", 0), 4), sol_from_sponsor=round(from_infra.get("спонсор", 0), 4),
                          sol_from_treasury=round(from_infra.get("казна", 0), 4), sol_to_infra=round(sum(to_infra.values()), 4),
                          transfers_in_17_11=len(got), pools_18_11=len(pools18),
                          pools_6e7X=sum(1 for q in pools18 if pool_creator.get(q) == C6), pools_GLEB=sum(1 for q in pools18 if pool_creator.get(q) == CG),
                          received_from_6e7X_or_GLEB=sum(1 for r in got if r["source"] in TARGETS.values())))
with open(os.path.join(OUT, "bot_creator_overlap.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(park_rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(park_rows)

# ---------- creator_connections.csv ----------
CC = []
def add(a, b, kind, evidence, sig="", slot="", unix="", sol="", alt="", conf=""):
    CC.append(dict(address_a=a, address_b=b, kind=kind, evidence=evidence, signature=sig, slot=slot, time_utc=iso(unix) if unix != "" else "",
                   sol=sol, alternative=alt, confidence=conf))
# (a) direct transfers between the two creators / with the infra — only possible in the 17.11 export
direct = [r for r in transfers if {r["source"], r["destination"]} & set(TARGETS.values())]
for r in direct:
    add(r["source"], r["destination"], "прямой перевод", "sol_export_transfers.csv", r["signature"], r["slot"], r["blockTime"], r["amount"],
        "", "высокая (подпись в данных)")
# (b) same live pattern: a >= 20 SOL transfer with the treasury/sponsor, then a pool with the creator's own 35 SOL buy
for k, v in TARGETS.items():
    for e in [e for e in log_events if e["wallet"] == v or e["wallet"].startswith(k)]:
        firsts = sorted((created.get(p, 0), p) for p, t, s in pools_of.get(v, []) if created.get(p))
        nxt = next(((tc, p) for tc, p in firsts if tc >= e["unix"] - 5), None)
        add(v, TREASURY + " / " + SPONSOR, "перевод ≥20 SOL с казной или спонсором (наблюдатель)", f"{e['source']}: «{e['text']}»", "", "", round(e["unix"]),
            "≥20", "направление и сумма в журнале не записаны; казна/спонсор могли получать возврат от создателя",
            "средняя: событие записано нашей программой, подписи нет" + (f"; следующий пул {nxt[1][:8]} через {nxt[0] - e['unix']:.0f} с" if nxt else ""))
# (c) identical first-second behaviour
for k, v in TARGETS.items():
    own = [s for p, t, s in pools_of.get(v, [])]
    add(v, "Семья 1", "одинаковая первая покупка создателя", f"пулов {len(own)}, собственные покупки в 1-ю секунду: {sorted(set(round(x, 2) for x in own))} SOL", "", "", "", "",
        "одинаковый шаблон запуска мог быть у разных операторов, использующих один скрипт", "средняя")
# (d) common park in their pools
p6 = {r["who"] for r in buys if pool_creator.get(r["pool"]) == C6 and r["who"] in PARK}
pG = {r["who"] for r in buys if pool_creator.get(r["pool"]) == CG and r["who"] in PARK}
add(C6, CG, "общие кошельки парка в их пулах", f"в пулах 6e7X — {len(p6)}, в пулах GLEB — {len(pG)}, общих {len(p6 & pG)} (Жаккар {len(p6 & pG) / max(1, len(p6 | pG)):.2f})",
    "", "", "", "", "общие покупатели могут быть независимыми ботами, торгующими любые свежие пулы (но в пулах других семей их нет)", "высокая (факт), связь владельцев — не доказана")
# (e) creators trading in each other's pools
x6 = [r for r in buys if r["who"] == C6 and pool_creator.get(r["pool"]) != C6]
xG = [r for r in buys if r["who"] == CG and pool_creator.get(r["pool"]) != CG]
add(C6, CG, "создатель покупал в чужих пулах", f"6e7X в чужих пулах: {len(x6)} сделок; GLEB в чужих пулах: {len(xG)} сделок", "", "", "", "", "", "высокая (факт)")
with open(os.path.join(OUT, "creator_connections.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(CC[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(CC)

# ---------- numbers for the report ----------
n_park17 = sum(1 for r in park_rows if r["group_17_11"] != "нет в выгрузке 17.11")
n_from_gc = sum(1 for r in park_rows if r["sol_from_gekko_creator"] > 0)
n_from_sp = sum(1 for r in park_rows if r["sol_from_sponsor"] > 0)
n_from_tr = sum(1 for r in park_rows if r["sol_from_treasury"] > 0)
grp = collections.Counter(r["group_17_11"] for r in park_rows)
sp_in_park = SPONSOR in PARK
sp_pools = sum(1 for q in {r["pool"] for r in buys if r["who"] == SPONSOR and r["kind"] == "buy"})
infra_edges = [(s, d, v) for (s, d), v in edges.items() if s in INFRA and d in INFRA]
res = dict(C6=C6, CG=CG, park=len(PARK), park17=n_park17, from_gc=n_from_gc, from_sp=n_from_sp, from_tr=n_from_tr, groups=dict(grp),
           sponsor_in_park=sp_in_park, sponsor_pools=sp_pools, direct=len(direct), raw_hits=[(h, t.get("slot"), t.get("blockTime")) for h, t in raw_hits][:20],
           logs=[e for e in log_events if e["wallet"][:8] in FAM1 or e["wallet"] in FAM1.values()], pools6=len(pools_of.get(C6, [])), poolsG=len(pools_of.get(CG, [])),
           p6=len(p6), pG=len(pG), common=len(p6 & pG), x6=len(x6), xG=len(xG), window=(iso(t_lo), iso(t_hi)), gekko_creator=gekko_creator,
           infra_edges=[(INFRA[s], INFRA[d], round(v[0], 2), v[1]) for s, d, v in infra_edges], ft=len(FT),
           first_pool_after_log={k: [] for k in TARGETS})
for k, v in TARGETS.items():
    for e in res["logs"]:
        if e["wallet"] == v or e["wallet"].startswith(k):
            firsts = sorted((created.get(p, 0), p) for p, t, s in pools_of.get(v, []) if created.get(p))
            nxt = next(((tc, p) for tc, p in firsts if tc >= e["unix"] - 5), None)
            res["first_pool_after_log"][k].append((e["iso"], nxt[1] if nxt else None, round(nxt[0] - e["unix"]) if nxt else None, iso(nxt[0]) if nxt else None))
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)[:4000])
