"""Task 11: funding of the nine vs the coins they trade. RPC only to find the creator of pools not covered by task 9
(oldest tx of the pool; Helius, HELIUS_KEY of D:\\bot\\.env, never printed; cache analysis/inv11_cache.json).
- coin sessions (the nine trade one coin at a time): first/last trade, creator of the coin's pool, net SOL of the nine into the pool;
- funding events (direct SOL transfers creator -> nine) and returns (nine -> creator), grouped into waves (>60 s gap);
- for every session: the last funding wave before it (who funded), is the funder = the coin's creator, seconds since the wave;
- per creator: SOL given to the nine, SOL returned, net SOL the nine put into this creator's pools, burns paid, rent received.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_11\\"""
import collections, csv, datetime as dt, gzip, json, os, statistics, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, "investigation_task_11")
os.makedirs(OUT, exist_ok=True)
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
H = "https://mainnet.helius-rpc.com/?api-key=" + K
LK, LAST, CALLS = threading.Lock(), [0.0], [0]


def rpc(m, p):
    for k in range(6):
        with LK:
            g = 0.12 - (time.time() - LAST[0])
            if g > 0:
                time.sleep(g)
            LAST[0] = time.time()
            CALLS[0] += 1
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(H, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                                         headers={"Content-Type": "application/json"}), timeout=90).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
        time.sleep(1 + k)
    return None


NINE = [r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))]
N = set(NINE)
legs = [l for l in rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv")) if l["signer"] in N and l["mint"]]
t9 = {r["mint"]: r for r in rd(os.path.join(D, r"investigation_task_09\coin_entry_summary.csv"))}
CACHE = os.path.join(A, "inv11_cache.json")
C = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
first_leg = {}
for l in sorted(legs, key=lambda l: int(l["slot"])):
    first_leg.setdefault(l["mint"], l)


def pool_creator(mt):
    l = first_leg[mt]
    out, before = [], l["signature"]
    for _ in range(5):
        page = rpc("getSignaturesForAddress", [l["pool"], {"before": before, "limit": 1000}]) or []
        out += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    ok = sorted([x for x in out if not x.get("err")], key=lambda x: x["slot"])
    res = dict(pool=l["pool"], before=len(out), complete=len(out) < 5000)
    for x in ok[:5]:
        t = rpc("getTransaction", [x["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
        if not t:
            continue
        logs = " ".join(t["meta"].get("logMessages") or [])
        if "CreatePool" in logs or "InitializePool" in logs or ("initialize" in logs.lower() and "pool" in logs.lower()):
            res.update(created_by=t["transaction"]["message"]["accountKeys"][0]["pubkey"], created_time=t["blockTime"], create_sig=x["signature"])
            break
    if "created_by" not in res and ok:
        res.update(oldest_seen=ok[0]["signature"], oldest_time=ok[0].get("blockTime"))
    C[mt] = res


todo = [m for m in first_leg if m not in t9 and m not in C]
print("монет", len(first_leg), "создатель из задания 9:", sum(1 for m in first_leg if m in t9), "ищу:", len(todo), flush=True)
with ThreadPoolExecutor(3) as ex:
    list(ex.map(pool_creator, todo))
json.dump(C, open(CACHE, "w", encoding="utf-8"))
creator, created_at = {}, {}
for mt in first_leg:
    if mt in t9 and t9[mt]["created_by"]:
        creator[mt] = t9[mt]["created_by"]
        try:
            created_at[mt] = int(dt.datetime.strptime(t9[mt]["pool_created_utc"][:20], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())
        except Exception:
            pass
    elif C.get(mt, {}).get("created_by"):
        creator[mt] = C[mt]["created_by"]
        created_at[mt] = C[mt]["created_time"]
print("создатель найден для", len(creator), "из", len(first_leg), "запросов", CALLS[0], flush=True)

# sessions
sess = collections.defaultdict(lambda: dict(t0=None, t1=None, txs=set(), net=0.0, wallets=set(), program=""))
for l in legs:
    s = sess[l["mint"]]
    t = int(l["blockTime"])
    s["t0"] = t if s["t0"] is None else min(s["t0"], t)
    s["t1"] = t if s["t1"] is None else max(s["t1"], t)
    s["txs"].add(l["signature"])
    s["net"] += float(l["wsol_to_pool"]) - float(l["wsol_from_pool"])
    s["wallets"].add(l["signer"])
    s["program"] = l["program"]
# funding / returns from raw tx (direct system transfers between creators/others and the nine), any signer
OKS = {x["signature"] for v in json.load(open(os.path.join(A, "inv07_sigs.json"), encoding="utf-8")).values() for x in v if not x["err"]}
CRE = set(creator.values()) | {"Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL", "6e7XUsDbJyxMdDe8zEHHMgWxkC73YAe428mJRSV65sSC", "29iqxoNvRDdx8G5peK3FbDVVt4mayaKKAesvn7m6R9ko",
                                 "CPC8iEE1PripNpd7VjofSHENYnoKpFnjmZFDtE8m7QT2", "89coAVTUZetQ4K6Ct4nsqtLtMCaR4X2mWStdBsmdECur"}
flows, seen = [], set()
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d["signature"] not in OKS or d["signature"] in seen:
            continue
        seen.add(d["signature"])
        t = d["tx"]
        ins_all = list(t["transaction"]["message"]["instructions"]) + [x for g in t["meta"].get("innerInstructions") or [] for x in g["instructions"]]
        for ins in ins_all:
            p = ins.get("parsed")
            if isinstance(p, dict) and ins.get("program") == "system" and p.get("type") == "transfer":
                a, b, v = p["info"]["source"], p["info"]["destination"], int(p["info"]["lamports"]) / 1e9
                if a in CRE and b in N:
                    flows.append(("funding", a, b, v, t["blockTime"], t["slot"], d["signature"]))
                elif a in N and b in CRE:
                    flows.append(("return", b, a, v, t["blockTime"], t["slot"], d["signature"]))
flows.sort(key=lambda x: (x[5], x[6]))


def waves(kind):
    out, cur = [], []
    for x in [f for f in flows if f[0] == kind]:
        if cur and (x[4] - cur[-1][4] > 60 or x[1] != cur[-1][1]):
            out.append(cur)
            cur = []
        cur.append(x)
    if cur:
        out.append(cur)
    return [dict(kind=kind, creator=w[0][1], start_unix=w[0][4], start_utc=iso(w[0][4]), end_utc=iso(w[-1][4]), transfers=len(w), wallets=len({x[2] for x in w}),
                 sol=round(sum(x[3] for x in w), 6), amounts=" ".join(f"{a}×{n}" for a, n in collections.Counter(round(x[3], 4) for x in w).most_common(3)),
                 first_signature=w[0][6]) for w in out]


FW, RW = waves("funding"), waves("return")
# burns per creator (task 8) and rent
ev = rd(os.path.join(D, r"investigation_task_08\burn_close_evidence.csv"))
burn_by = collections.Counter(e["fee_payer"] for e in ev if e["op"] == "burn")
rent_by = collections.Counter()
for e in ev:
    if e["op"] == "closeAccount" and str(e["lamports_refunded"]).isdigit() and e["rent_destination"] not in N:
        rent_by[e["rent_destination"]] += int(e["lamports_refunded"]) / 1e9

srows = []
for mt, s in sorted(sess.items(), key=lambda kv: kv[1]["t0"]):
    prev_f = [w for w in FW if w["start_unix"] <= s["t0"]]
    lf = prev_f[-1] if prev_f else None
    nxt = [w for w in RW if w["start_unix"] >= s["t0"]]
    cr = creator.get(mt, "")
    srows.append(dict(mint=mt, creator=cr, program=s["program"], session_start_utc=iso(s["t0"]), session_end_utc=iso(s["t1"]), session_s=s["t1"] - s["t0"],
                      txs=len(s["txs"]), wallets=len(s["wallets"]), net_sol_into_pool=round(s["net"], 6),
                      seconds_pool_created_to_session=(s["t0"] - created_at[mt]) if mt in created_at else "",
                      last_funding_creator=lf["creator"] if lf else "", last_funding_utc=lf["start_utc"] if lf else "", seconds_since_funding=(s["t0"] - lf["start_unix"]) if lf else "",
                      funder_is_coin_creator=int(bool(lf) and lf["creator"] == cr) if cr else "",
                      next_return_creator=nxt[0]["creator"] if nxt else "", next_return_utc=nxt[0]["start_utc"] if nxt else ""))


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


wcsv("coin_sessions.csv", srows)
wcsv("funding_waves.csv", FW)
wcsv("return_waves.csv", RW)
# per creator balance
crs = sorted(set(creator.values()) | {w["creator"] for w in FW + RW} | set(burn_by) - N)
crow = []
for c in crs:
    crow.append(dict(creator=c, coins_created=sum(1 for m in sess if creator.get(m) == c), sessions_txs=sum(len(s["txs"]) for m, s in sess.items() if creator.get(m) == c),
                     net_sol_nine_into_its_pools=round(sum(s["net"] for m, s in sess.items() if creator.get(m) == c), 6),
                     funded_to_nine=round(sum(w["sol"] for w in FW if w["creator"] == c), 6), funding_waves=sum(1 for w in FW if w["creator"] == c),
                     returned_from_nine=round(sum(w["sol"] for w in RW if w["creator"] == c), 6), return_waves=sum(1 for w in RW if w["creator"] == c),
                     burns_paid=burn_by.get(c, 0), rent_received=round(rent_by.get(c, 0), 6)))
crow.sort(key=lambda r: -r["net_sol_nine_into_its_pools"])
wcsv("creator_balance.csv", crow)
# timeline: interleave funding / return waves and sessions
tl = [dict(utc=w["start_utc"], event=("пополнение" if w["kind"] == "funding" else "возврат"), creator=w["creator"], detail=f"{w['wallets']} кош., {w['sol']} SOL ({w['amounts']})")
      for w in FW + RW]
tl += [dict(utc=r["session_start_utc"], event="торговля монетой", creator=r["creator"], detail=f"{r['mint'][:8]}… {r['txs']} tx, {r['session_s']} с, поток {r['net_sol_into_pool']} SOL")
       for r in srows]
tl.sort(key=lambda r: r["utc"])
wcsv("timeline.csv", tl)
known = [r for r in srows if r["creator"] and r["last_funding_creator"]]
big = [r for r in known if r["txs"] >= 20]
res = dict(coins=len(sess), creator_found=len(creator), creators=dict(collections.Counter(creator.values()).most_common()),
           funding_waves=len(FW), return_waves=len(RW), funding_by=dict(collections.Counter(w["creator"][:8] for w in FW)),
           sessions_with_known_funder=len(known), funder_is_coin_creator=sum(r["funder_is_coin_creator"] for r in known),
           sessions_20tx=len(big), funder_is_coin_creator_20tx=sum(r["funder_is_coin_creator"] for r in big),
           pool_created_to_session_s=sorted(r["seconds_pool_created_to_session"] for r in srows if r["seconds_pool_created_to_session"] != ""),
           calls=CALLS[0])
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
for r in crow:
    print(r)
