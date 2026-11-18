"""Task 11 — corrections (analyst's review). Original task 11 files are not changed; output goes to investigation_task_11/v2/.
1) pool_init_payer (fee payer of the pool-initialisation tx; was "created_by") + on-chain fields of the PumpSwap pool account:
   creator (offset 11) and coin_creator (offset 211) — getMultipleAccounts (Helius, HELIUS_KEY of D:\\bot\\.env, never printed).
2) ALL direct SOL transfers (system transfer, any depth) INTO the nine from any address, and from the nine to any address, in all 12 226 tx.
3) last funder per session recomputed from all sources: variant A every incoming transfer; variant B only transfers >= 0.1 SOL.
   Sessions = activity of the nine per coin split at gaps > 120 s (task 10 validation).
4) significance with the time structure preserved. H0: the sequence of coin creators (pool_init_payer) and the sequence of last funders are
   independent processes, each with its own temporal autocorrelation (shifts).
   a) circular shift: the funder sequence is rotated against the creator sequence by k = 1..n-1 sessions; p = share of rotations with >= observed matches;
   b) block permutation: funder sequence cut into its runs (maximal blocks of equal funder), blocks shuffled 5000 times (seed 11), sessions keep order;
   c) naive permutation of single sessions (as in the first report; independence assumed — kept for comparison).
   All values of every null distribution are saved.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_11\\v2\\"""
import base64, collections, csv, datetime as dt, gzip, json, os, random, statistics, sys, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, r"investigation_task_11\v2")
os.makedirs(OUT, exist_ok=True)
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
H = "https://mainnet.helius-rpc.com/?api-key=" + K


def rpc(m, p):
    for _ in range(5):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(H, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                                         headers={"Content-Type": "application/json"}), timeout=90).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
    return None


def b58enc(b):
    n = int.from_bytes(b, "big")
    s = ""
    while n:
        n, r = divmod(n, 58)
        s = B58[r] + s
    return "1" * (len(b) - len(b.lstrip(b"\0"))) + s


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


NINE = [r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))]
N = set(NINE)
legs = [l for l in rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv")) if l["signer"] in N and l["mint"]]
S11 = {r["mint"]: r for r in rd(os.path.join(D, r"investigation_task_11\coin_sessions.csv"))}
pool_of, prog_of = {}, {}
for l in legs:
    pool_of[l["mint"]], prog_of[l["mint"]] = l["pool"], l["program"]
# ---- 1) pool init payer + on-chain pool fields ----
mints = sorted(pool_of)
pools = [pool_of[m] for m in mints]
acc = {}
for i in range(0, len(pools), 100):
    res = rpc("getMultipleAccounts", [pools[i:i + 100], {"encoding": "base64"}]) or {}
    for p, v in zip(pools[i:i + 100], res.get("value") or []):
        acc[p] = v
prow = []
for m in mints:
    p = pool_of[m]
    v = acc.get(p)
    creator = coin_creator = owner = ""
    if v:
        owner = v["owner"]
        data = base64.b64decode(v["data"][0])
        if owner == "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA" and len(data) >= 243:
            creator, coin_creator = b58enc(data[11:43]), b58enc(data[211:243])
            if b58enc(data[43:75]) not in ("So11111111111111111111111111111111111111112", m) and b58enc(data[75:107]) not in ("So11111111111111111111111111111111111111112", m):
                creator = coin_creator = "раскладка не совпала"
    payer = S11[m]["creator"] if m in S11 else ""
    prow.append(dict(mint=m, pool=p, program=prog_of[m], pool_account_owner=owner, pool_init_payer=payer, pool_field_creator=creator, pool_field_coin_creator=coin_creator,
                     payer_eq_pool_creator=int(bool(payer) and payer == creator) if creator else "", payer_eq_coin_creator=int(bool(payer) and payer == coin_creator) if coin_creator else ""))
wcsv("pool_creator_fields.csv", prow)
init_payer = {r["mint"]: r["pool_init_payer"] for r in prow}

# ---- 2) all direct SOL transfers into / out of the nine ----
OKS = {x["signature"] for v in json.load(open(os.path.join(A, "inv07_sigs.json"), encoding="utf-8")).values() for x in v if not x["err"]}
inc, outg, seen = [], [], set()
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d["signature"] not in OKS or d["signature"] in seen:
            continue
        seen.add(d["signature"])
        t = d["tx"]
        payer = t["transaction"]["message"]["accountKeys"][0]["pubkey"]
        allins = [(0, x) for x in t["transaction"]["message"]["instructions"]] + [(1, x) for g in t["meta"].get("innerInstructions") or [] for x in g["instructions"]]
        for depth, ins in allins:
            p = ins.get("parsed")
            if not (isinstance(p, dict) and ins.get("program") == "system" and p.get("type") == "transfer"):
                continue
            a, b, v = p["info"]["source"], p["info"]["destination"], int(p["info"]["lamports"]) / 1e9
            row = dict(signature=d["signature"], slot=t["slot"], unix=t["blockTime"], time_utc=iso(t["blockTime"]), source=a, destination=b, sol=v, fee_payer=payer,
                       inner=depth)
            if b in N and a not in N:
                inc.append(row)
            elif a in N and b not in N:
                outg.append(row)
inc.sort(key=lambda r: (r["slot"], r["signature"]))
outg.sort(key=lambda r: (r["slot"], r["signature"]))
wcsv("incoming_sol_all.csv", inc)
wcsv("outgoing_sol_all.csv", outg)
src = collections.defaultdict(lambda: [0, 0.0, set(), None, None])
for r in inc:
    e = src[r["source"]]
    e[0] += 1
    e[1] += r["sol"]
    e[2].add(r["destination"])
    e[3] = r["time_utc"] if e[3] is None else min(e[3], r["time_utc"])
    e[4] = r["time_utc"] if e[4] is None else max(e[4], r["time_utc"])
srows = sorted([dict(source=k, transfers=v[0], sol=round(v[1], 9), wallets=len(v[2]), first_utc=v[3], last_utc=v[4],
                     is_pool_init_payer=int(k in set(init_payer.values()))) for k, v in src.items()], key=lambda r: -r["sol"])
wcsv("incoming_sources.csv", srows)

# ---- 3) sessions with gap 120 s and last funder (A: any, B: >= 0.1 SOL) ----
by = collections.defaultdict(list)
for l in legs:
    by[l["mint"]].append(int(l["blockTime"]))
sess = []
for m, ts in by.items():
    ts = sorted(set(ts))
    cur = [ts[0]]
    for t in ts[1:]:
        if t - cur[-1] > 120:
            sess.append((m, cur[0], cur[-1]))
            cur = [t]
        else:
            cur.append(t)
    sess.append((m, cur[0], cur[-1]))
sess.sort(key=lambda s: s[1])


def last_funder(t0, minsol):
    c = [r for r in inc if r["unix"] <= t0 and r["sol"] >= minsol]
    return (c[-1]["source"], c[-1]["time_utc"], c[-1]["sol"]) if c else ("", "", "")


rows = []
for m, t0, t1 in sess:
    fa, fta, fsa = last_funder(t0, 0)
    fb, ftb, fsb = last_funder(t0, 0.1)
    pip = init_payer.get(m, "")
    rows.append(dict(mint=m, pool_init_payer=pip, session_start_utc=iso(t0), session_end_utc=iso(t1), session_s=t1 - t0,
                     last_funder_any=fa, last_funder_any_utc=fta, last_funder_any_sol=fsa, match_any=int(bool(pip) and fa == pip) if pip and fa else "",
                     last_funder_ge01=fb, last_funder_ge01_utc=ftb, last_funder_ge01_sol=fsb, match_ge01=int(bool(pip) and fb == pip) if pip and fb else ""))
wcsv("sessions_gap120.csv", rows)


# ---- 4) tests ----
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


tests = {}
random.seed(11)
for key, col in (("any", "last_funder_any"), ("ge01", "last_funder_ge01")):
    R = [r for r in rows if r["pool_init_payer"] and r[col]]
    cr = [r["pool_init_payer"] for r in R]
    fu = [r[col] for r in R]
    n = len(R)
    obs = sum(a == b for a, b in zip(cr, fu))
    circ = [sum(a == b for a, b in zip(cr, fu[k:] + fu[:k])) for k in range(1, n)]
    blocks = runs(fu)
    bperm = []
    for _ in range(5000):
        bl = blocks[:]
        random.shuffle(bl)
        f2 = [x for b in bl for x in b]
        bperm.append(sum(a == b for a, b in zip(cr, f2)))
    naive = []
    for _ in range(5000):
        f2 = fu[:]
        random.shuffle(f2)
        naive.append(sum(a == b for a, b in zip(cr, f2)))
    tests[key] = dict(sessions=n, observed=obs, funder_blocks=len(blocks), creator_blocks=len(runs(cr)),
                      circular=dict(rotations=len(circ), mean=round(statistics.mean(circ), 2), max=max(circ), p=sum(1 for x in circ if x >= obs) / len(circ)),
                      block_perm=dict(n=5000, mean=round(statistics.mean(bperm), 2), p95=sorted(bperm)[4750], max=max(bperm), p=(sum(1 for x in bperm if x >= obs) + 1) / 5001),
                      naive_perm=dict(n=5000, mean=round(statistics.mean(naive), 2), max=max(naive), p=(sum(1 for x in naive if x >= obs) + 1) / 5001))
    with open(os.path.join(OUT, f"null_distributions_{key}.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["test", "i", "matches"])
        for i, x in enumerate(circ, 1):
            w.writerow(["circular_shift", i, x])
        for i, x in enumerate(bperm, 1):
            w.writerow(["block_permutation", i, x])
        for i, x in enumerate(naive, 1):
            w.writerow(["naive_permutation", i, x])
# money: per pool_init_payer net funding (all sources by address) vs net flow into their pools
flow = collections.defaultdict(float)
for l in legs:
    flow[init_payer.get(l["mint"], "")] += float(l["wsol_to_pool"]) - float(l["wsol_from_pool"])
inn = collections.Counter()
for r in inc:
    inn[r["source"]] += r["sol"]
out_ = collections.Counter()
for r in outg:
    out_[r["destination"]] += r["sol"]
money = sorted([dict(address=a, sol_in_to_nine=round(inn[a], 6), sol_out_from_nine=round(out_[a], 6), net_given=round(inn[a] - out_[a], 6),
                     net_flow_of_nine_into_its_pools=round(flow.get(a, 0), 6), coins_initialised=sum(1 for v in init_payer.values() if v == a))
                for a in set(inn) | set(out_) | {v for v in init_payer.values() if v}], key=lambda r: -abs(r["net_given"]))
wcsv("money_by_address.csv", money)
res = dict(pools=len(prow), pumpswap_pools=sum(1 for r in prow if r["pool_field_creator"]),
           payer_eq_pool_creator=sum(1 for r in prow if r["payer_eq_pool_creator"] == 1), payer_eq_coin_creator=sum(1 for r in prow if r["payer_eq_coin_creator"] == 1),
           pool_creator_eq_coin_creator=sum(1 for r in prow if r["pool_field_creator"] and r["pool_field_creator"] == r["pool_field_coin_creator"]),
           incoming_transfers=len(inc), incoming_sources=len(srows), incoming_top=srows[:12], sessions_gap120=len(rows),
           match_any=f"{sum(1 for r in rows if r['match_any'] == 1)}/{sum(1 for r in rows if r['match_any'] != '')}",
           match_ge01=f"{sum(1 for r in rows if r['match_ge01'] == 1)}/{sum(1 for r in rows if r['match_ge01'] != '')}", tests=tests)
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
