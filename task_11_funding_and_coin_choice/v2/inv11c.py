"""Task 11 v2.1 — fixes after the second review. Reads investigation_task_11/v2 files (not changed), writes new files next to them.
1) pool creator for statistics: PumpSwap -> on-chain pool field `creator`; Meteora (7) -> pool_init_payer, marked creator_source.
2) exact tests: all 5! block permutations of the funder shifts (no sampling); circular shift INCLUDING the original position (k = 0..n-1);
   for all sessions and for PumpSwap-only sessions; every value saved.
3) mint_authority_check.csv: all 85 mints (getMultipleAccounts jsonParsed): owner program, mint authority, freeze authority, decimals, supply.
4) mint_init.csv: the oldest transaction of every mint before the nine's first trade (getSignaturesForAddress(mint, before=first nine tx), paged
   back) -> does it contain InitializeMint/InitializeMint2, its fee payer, the mint authority set at initialisation, time vs pool creation.
Helius (HELIUS_KEY of D:\\bot\\.env, never printed); cache analysis/inv11c_cache.json."""
import collections, csv, datetime as dt, itertools, json, os, statistics, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
V2 = os.path.join(D, r"investigation_task_11\v2")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
H = "https://mainnet.helius-rpc.com/?api-key=" + K


def rpc(m, p):
    for k in range(8):
        try:
            r = json.loads(urllib.request.urlopen(urllib.request.Request(H, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                                         headers={"Content-Type": "application/json"}), timeout=90).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
        time.sleep(1 + 2 * k)
    return None


def wcsv(name, rows):
    with open(os.path.join(V2, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rows)


PF = {r["mint"]: r for r in rd(os.path.join(V2, "pool_creator_fields.csv"))}
SES = rd(os.path.join(V2, "sessions_gap120.csv"))
CACHE = os.path.join(A, "inv11c_cache.json")
C = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

# ---- 1) creator per session ----
rows = []
for s in SES:
    p = PF.get(s["mint"], {})
    if p.get("pool_field_creator") and p["pool_field_creator"] != "раскладка не совпала":
        cr, srcn = p["pool_field_creator"], "поле creator пула PumpSwap"
    else:
        cr, srcn = s["pool_init_payer"], "плательщик инициализации (Meteora, поле не декодировано)"
    fu = s["last_funder_ge01"]
    rows.append(dict(mint=s["mint"], program=p.get("program", ""), creator=cr, creator_source=srcn, session_start_utc=s["session_start_utc"],
                     session_end_utc=s["session_end_utc"], last_funder_ge01=fu, last_funder_ge01_utc=s["last_funder_ge01_utc"],
                     match=int(cr == fu) if cr and fu else "", note="" if fu else "торговля началась до первого пополнения (≥0.1 SOL) — в тест не входит"))
wcsv("sessions_gap120_v21.csv", rows)


# ---- 2) exact tests ----
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


tests, nulls = {}, []
for name, R in (("все сессии", [r for r in rows if r["match"] != ""]), ("только PumpSwap", [r for r in rows if r["match"] != "" and r["program"] == "PumpSwap"])):
    cr = [r["creator"] for r in R]
    fu = [r["last_funder_ge01"] for r in R]
    n = len(R)
    obs = sum(a == b for a, b in zip(cr, fu))
    circ = [sum(a == b for a, b in zip(cr, fu[k:] + fu[:k])) for k in range(n)]  # k = 0 is the observed arrangement
    blocks = runs(fu)
    perm = []
    for order in itertools.permutations(range(len(blocks))):
        f2 = [x for i in order for x in blocks[i]]
        perm.append(sum(a == b for a, b in zip(cr, f2)))
    tests[name] = dict(sessions=n, observed=obs, share=round(obs / n, 4), funder_shifts=len(blocks), shift_lengths=[len(b) for b in blocks],
                       circular=dict(positions=n, ge_observed=sum(1 for x in circ if x >= obs), p=round(sum(1 for x in circ if x >= obs) / n, 4), mean=round(statistics.mean(circ), 2)),
                       shift_permutations=dict(all=len(perm), ge_observed=sum(1 for x in perm if x >= obs), p=round(sum(1 for x in perm if x >= obs) / len(perm), 4),
                                               mean=round(statistics.mean(perm), 2)))
    nulls += [dict(sample=name, test="circular_shift", index=k, matches=x) for k, x in enumerate(circ)]
    nulls += [dict(sample=name, test="shift_permutation", index=i, matches=x) for i, x in enumerate(perm)]
wcsv("null_distributions_exact.csv", nulls)

# ---- 3) mint authority ----
mints = sorted(PF)
acc = {}
for i in range(0, len(mints), 100):
    v = rpc("getMultipleAccounts", [mints[i:i + 100], {"encoding": "jsonParsed"}]) or {}
    for m, a in zip(mints[i:i + 100], v.get("value") or []):
        acc[m] = a
mrows = []
for m in mints:
    a = acc.get(m)
    info = a["data"]["parsed"]["info"] if a and isinstance(a.get("data"), dict) else {}
    mrows.append(dict(mint=m, owner_program=a["owner"] if a else "нет ответа", mint_authority=info.get("mintAuthority") or "отозван (None)",
                      freeze_authority=info.get("freezeAuthority") or "отозван (None)", decimals=info.get("decimals", ""), supply=info.get("supply", ""),
                      result="оба полномочия отозваны" if a and not info.get("mintAuthority") and not info.get("freezeAuthority") else "проверить"))
wcsv("mint_authority_check.csv", mrows)

# ---- 4) mint initialisation ----
legs = rd(os.path.join(D, r"investigation_task_07\nine_swap_legs.csv"))
first_sig = {}
for l in sorted(legs, key=lambda l: int(l["slot"])):
    if l["mint"]:
        first_sig.setdefault(l["mint"], l["signature"])
irows = []
for m in mints:
    if m not in C:
        sigs, before = [], first_sig.get(m)
        for _ in range(10):
            p = {"limit": 1000}
            if before:
                p["before"] = before
            page = rpc("getSignaturesForAddress", [m, p]) or []
            sigs += page
            if len(page) < 1000:
                break
            before = page[-1]["signature"]
        ok = sorted([x for x in sigs if not x.get("err")], key=lambda x: x["slot"])
        rec = dict(scanned=len(sigs), complete=len(sigs) < 10000)
        if ok:
            t = rpc("getTransaction", [ok[0]["signature"], {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
            if t:
                logs = " ".join(t["meta"].get("logMessages") or [])
                ma = ""
                for ins in list(t["transaction"]["message"]["instructions"]) + [x for g in t["meta"].get("innerInstructions") or [] for x in g["instructions"]]:
                    pp = ins.get("parsed")
                    if isinstance(pp, dict) and pp.get("type", "").startswith("initializeMint") and pp["info"].get("mint") == m:
                        ma = pp["info"].get("mintAuthority", "")
                rec.update(signature=ok[0]["signature"], slot=ok[0]["slot"], time=t.get("blockTime"), fee_payer=t["transaction"]["message"]["accountKeys"][0]["pubkey"],
                           has_init_mint=int("InitializeMint" in logs), mint_authority_at_init=ma, also_creates_pool=int("CreatePool" in logs))
        C[m] = rec
        json.dump(C, open(CACHE, "w", encoding="utf-8"))
    r = C[m]
    pc = PF[m]
    creator = pc["pool_field_creator"] or pc["pool_init_payer"]
    irows.append(dict(mint=m, program=pc["program"], signatures_scanned=r.get("scanned"), oldest_signature=r.get("signature", ""), oldest_utc=iso(r["time"]) if r.get("time") else "",
                      oldest_has_InitializeMint=r.get("has_init_mint", ""), mint_init_fee_payer=r.get("fee_payer", ""), mint_authority_at_init=r.get("mint_authority_at_init", ""),
                      same_tx_creates_pool=r.get("also_creates_pool", ""), pool_creator=creator,
                      mint_init_payer_eq_pool_creator=int(r.get("fee_payer") == creator) if r.get("fee_payer") and creator else "",
                      mint_authority_at_init_eq_pool_creator=int(r.get("mint_authority_at_init") == creator) if r.get("mint_authority_at_init") and creator else ""))
wcsv("mint_init.csv", irows)
res = dict(tests=tests, mints=len(mrows), both_revoked=sum(1 for r in mrows if r["result"] == "оба полномочия отозваны"),
           mint_owner_programs=dict(collections.Counter(r["owner_program"] for r in mrows)),
           init_found=sum(1 for r in irows if r["oldest_has_InitializeMint"] == 1), init_payer_eq_pool_creator=sum(1 for r in irows if r["mint_init_payer_eq_pool_creator"] == 1),
           init_authority_eq_pool_creator=sum(1 for r in irows if r["mint_authority_at_init_eq_pool_creator"] == 1),
           same_tx_creates_pool=sum(1 for r in irows if r["same_tx_creates_pool"] == 1),
           init_payers=dict(collections.Counter(r["mint_init_fee_payer"][:8] for r in irows).most_common(12)))
json.dump(res, open(os.path.join(V2, "_numbers_v21.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
