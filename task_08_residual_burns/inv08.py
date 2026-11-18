"""Task 08 (+ fixes to task 07), no RPC. Input: inv06_raw.jsonl.gz (all 12 226 successful tx of the nine, see inv07),
inv07_sigs.json, investigation_task_07/nine_swap_legs.csv and nine_tx_validation.csv.
1) cosigned_transactions.csv: every successful tx where a wallet of the nine SIGNS but does not pay the fee (fee payer, all signers, what it does).
2) burn_close_evidence.csv: every burn / burnChecked and every closeAccount (any depth) touching an account owned by one of the nine:
   signature, slot, fee payer, wallet, mint, token account, raw amount + decimals, closed account, rent destination, lamports refunded
   (= the closed account's lamports right before the close: preBalance + lamports created/transferred into it in the same tx).
3) Independent rent check for the nine's own tx: expected refund = lamports of accounts closed to the signer, from createAccount and
   preBalances, compared with the residual of inv07 (native change minus fee, rent paid, net WSOL into pools, transfers).
4) residual_positions.csv (task 8): per wallet x mint — coin received/sent in swaps (raw), token transfers in/out outside swaps (raw),
   burned (raw), last balance seen (raw), whether the account was closed, gap = swaps_net + in - out - burned - last_balance;
   delay from the last swap to the burn, fee payer of the burn vs creator of the coin.
5) slot ties: how many first/last balance rows of a wallet share the slot with another tx of the same wallet (order inside a slot unknown).
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_08\\"""
import collections, csv, datetime as dt, gzip, json, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
T7 = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_07"
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_08"
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
WSOL = "So11111111111111111111111111111111111111112"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
NINE = [r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv")]
N = set(NINE)
creator_of = {r["mint"]: r["creator"] for r in rd(os.path.join(A, "sol_pools.csv"))}
for r in rd(os.path.join(A, "sol_watch.csv")) if os.path.exists(os.path.join(A, "sol_watch.csv")) else []:
    if r.get("mint") and r.get("creator"):
        creator_of.setdefault(r["mint"], r["creator"])
for l in open(os.path.join(A, "sol_pool_rec.jsonl"), encoding="utf-8") if os.path.exists(os.path.join(A, "sol_pool_rec.jsonl")) else []:
    try:
        d = json.loads(l)
    except Exception:
        continue
    if d.get("mint") and d.get("creator"):
        creator_of.setdefault(d["mint"], d["creator"])
SIGS = json.load(open(os.path.join(A, "inv07_sigs.json"), encoding="utf-8"))
OK = {x["signature"] for v in SIGS.values() for x in v if not x["err"]}
txs = {}
with gzip.open(os.path.join(A, "inv06_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        if d["signature"] in OK:
            txs[d["signature"]] = d["tx"]
print("транзакций", len(txs), "из", len(OK))


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        wr.writeheader()
        wr.writerows(rows)


cos, ev, rentchk = [], [], []
tokmov = collections.defaultdict(lambda: collections.Counter())  # (wallet, mint) -> counters
lastbal = {}  # (wallet, mint) -> (slot, sig, raw, account)
closed_acc = {}  # account -> (slot, sig, destination)
acct_of = {}  # token account -> (owner, mint)
decs = {}
for sig, t in txs.items():
    m = t["meta"]
    msg = t["transaction"]["message"]
    ak = msg["accountKeys"]
    keys = [k["pubkey"] for k in ak]
    payer = keys[0]
    signers = [k["pubkey"] for k in ak if k.get("signer")]
    pre = {keys[i]: v for i, v in enumerate(m["preBalances"])}
    tb = {}
    for b in (m.get("preTokenBalances") or []) + (m.get("postTokenBalances") or []):
        tb[keys[b["accountIndex"]]] = (b["mint"], b.get("owner"), b["uiTokenAmount"]["decimals"])
        decs[b["mint"]] = b["uiTokenAmount"]["decimals"]
    inner = {g["index"]: g["instructions"] for g in m.get("innerInstructions") or []}
    flat = []  # (top index, depth tag, ins)
    for i, ins in enumerate(msg["instructions"]):
        flat.append((i, "top", ins))
        for x in inner.get(i, []):
            flat.append((i, "inner", x))
    for i, kind, ins in flat:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if isinstance(p, dict) and p.get("type") in ("initializeAccount", "initializeAccount2", "initializeAccount3"):
            inf = p["info"]
            tb.setdefault(inf["account"], (inf["mint"], inf.get("owner"), decs.get(inf["mint"])))
    for a, (mt, ow, dc) in tb.items():
        if ow:
            acct_of[a] = (ow, mt)
    swap_tops = {i for i, ins in enumerate(msg["instructions"]) if ins.get("programId") in (AMM, MET)}
    created = collections.Counter()
    created_n = collections.Counter()
    into = collections.Counter()
    for i, kind, ins in flat:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if not isinstance(p, dict):
            continue
        inf = p.get("info", {})
        if ins.get("program") == "system" and p.get("type") in ("createAccount", "createAccountWithSeed"):
            created[inf["newAccount"]] += int(inf["lamports"])
            created_n[inf["newAccount"]] += 1
        if ins.get("program") == "system" and p.get("type") == "transfer":
            into[inf["destination"]] += int(inf["lamports"])
    # burns / closes / token transfers outside swaps
    for i, kind, ins in flat:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if not (isinstance(p, dict) and str(ins.get("program", "")).startswith("spl-token")):
            continue
        typ, inf = p.get("type"), p.get("info", {})
        if typ in ("burn", "burnChecked"):
            acc = inf["account"]
            mint = inf.get("mint") or tb.get(acc, ("",))[0]
            owner = tb.get(acc, (None, None))[1] or inf.get("authority")
            amt = int(inf["tokenAmount"]["amount"]) if "tokenAmount" in inf else int(inf["amount"])
            if owner in N or inf.get("authority") in N:
                w = owner if owner in N else inf.get("authority")
                ev.append(dict(op="burn", signature=sig, slot=t["slot"], time_utc=iso(t["blockTime"]), fee_payer=payer, signers=" ".join(signers), wallet=w, mint=mint,
                               coin_creator=creator_of.get(mint, ""), token_account=acc, amount_raw=amt, decimals=decs.get(mint, ""), rent_destination="", lamports_refunded=""))
                tokmov[(w, mint)]["burned"] += amt
                tokmov[(w, mint)]["burn_n"] += 1
                tokmov[(w, mint)]["burn_slot"] = max(tokmov[(w, mint)]["burn_slot"], t["slot"])
                tokmov[(w, mint)]["burn_payer:" + payer] += 1
        elif typ == "closeAccount":
            acc, dst = inf["account"], inf["destination"]
            owner = inf.get("owner") or tb.get(acc, (None, None))[1]
            mint = tb.get(acc, ("",))[0]
            lam = pre.get(acc, 0) + created[acc] + into[acc]
            if owner in N:
                temp = created[acc] > 0
                ev.append(dict(op="closeAccount", signature=sig, slot=t["slot"], time_utc=iso(t["blockTime"]), fee_payer=payer, signers=" ".join(signers), wallet=owner,
                               mint=mint, coin_creator=creator_of.get(mint, ""), token_account=acc, amount_raw="", decimals="", rent_destination=dst,
                               lamports_refunded=lam if not temp else f"{lam} (счёт создан в этой же транзакции)"))
                if not temp:
                    closed_acc[acc] = (t["slot"], sig, dst)
        elif typ in ("transfer", "transferChecked") and i not in swap_tops:
            src, dst = inf["source"], inf["destination"]
            amt = int(inf["tokenAmount"]["amount"]) if "tokenAmount" in inf else int(inf["amount"])
            mint = inf.get("mint") or tb.get(src, tb.get(dst, ("",)))[0]
            so, do = tb.get(src, (None, None))[1], tb.get(dst, (None, None))[1]
            if so in N and mint != WSOL:
                tokmov[(so, mint)]["transfer_out"] += amt
            if do in N and mint != WSOL:
                tokmov[(do, mint)]["transfer_in"] += amt
    for b in m.get("postTokenBalances") or []:
        ow = b.get("owner")
        if ow in N and b["mint"] != WSOL:
            k = (ow, b["mint"])
            if k not in lastbal or t["slot"] > lastbal[k][0]:
                lastbal[k] = (t["slot"], sig, int(b["uiTokenAmount"]["amount"]), keys[b["accountIndex"]])
    nine_signers = [s for s in signers if s in N]
    if nine_signers and payer not in N:
        tr = []
        for i, kind, ins in flat:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and ins.get("program") == "system" and p.get("type") == "transfer":
                tr.append(f"{p['info']['source'][:8]}->{p['info']['destination'][:8]}:{int(p['info']['lamports']) / 1e9:g}")
        ops = collections.Counter(p.get("type") for _, _, x in flat for p in [x.get("parsed")] if isinstance(p, dict))
        cos.append(dict(signature=sig, slot=t["slot"], time_utc=iso(t["blockTime"]), fee_payer=payer, signers=" ".join(signers), nine_signers=len(nine_signers),
                        operations=" ".join(f"{k}×{v}" for k, v in ops.most_common()), sol_transfers=" ".join(tr)))
    # independent rent check (own tx of the nine)
    if payer in N:
        exp = 0
        for i, kind, ins in flat:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type") == "closeAccount" and p["info"].get("destination") == payer:
                acc = p["info"]["account"]
                # one creation's rent per close (the same temporary address is created and closed once per swap), or a pre-existing account's lamports
                exp += (created[acc] / created_n[acc]) if created_n[acc] else pre.get(acc, 0)
        rentchk.append((sig, exp / 1e9))
cos.sort(key=lambda r: (r["slot"], r["signature"]))
ev.sort(key=lambda r: (r["slot"], r["signature"], r["op"]))
wcsv("cosigned_transactions.csv", cos)
wcsv("burn_close_evidence.csv", ev)

# rent check vs inv07 residual
tv = {r["signature"]: r for r in rd(os.path.join(T7, "nine_tx_validation.csv"))}
rows = []
for sig, exp in rentchk:
    r = tv.get(sig)
    if not r:
        continue
    resid = float(r["residual_rent_refund_and_unexplained"])
    rows.append(dict(signature=sig, venue=r["venue"], residual_inv07=resid, expected_refund_from_closes=round(exp, 9), unexplained=round(resid - exp, 9)))
wcsv("rent_refund_check.csv", rows)
une = [abs(r["unexplained"]) for r in rows]

# residual positions (task 8)
legs = rd(os.path.join(T7, "nine_swap_legs.csv"))
sw = collections.defaultdict(lambda: [0, 0, 0, 0, None])  # bought raw, sold raw, legs, last swap slot, venue set
for l in legs:
    if l["signer"] not in N or not l["mint"]:
        continue
    k = (l["signer"], l["mint"])
    sw[k][0] += int(l["coin_from_pool_raw"] or 0)
    sw[k][1] += int(l["coin_to_pool_raw"] or 0) + (int(l["fee_coin_raw"] or 0) if l["side"] == "SELL" else 0)  # on a sell the user also pays the coin fees
    sw[k][2] += 1
    sw[k][3] = max(sw[k][3], int(l["slot"]))
    sw[k][4] = (sw[k][4] or set()) | {l["program"]}
slot_time = {}
for t in txs.values():
    slot_time[t["slot"]] = t["blockTime"]
pos = []
for k in sorted(set(sw) | set(tokmov) | set(lastbal)):
    w, mt = k
    b, s, n, lastslot, ven = sw.get(k, [0, 0, 0, 0, None])
    tm = tokmov.get(k, collections.Counter())
    lb = lastbal.get(k)
    acc = lb[3] if lb else ""
    cl = closed_acc.get(acc)
    last_raw = 0 if cl and lb and cl[0] >= lb[0] else (lb[2] if lb else 0)
    gap = b - s + tm["transfer_in"] - tm["transfer_out"] - tm["burned"] - last_raw
    payers = [x.split(":", 1)[1] for x in tm if str(x).startswith("burn_payer:")]
    bs = tm["burn_slot"] or 0
    pos.append(dict(wallet=w, mint=mt, coin_creator=creator_of.get(mt, ""), venues=" ".join(sorted(ven or [])), swap_legs=n, swap_bought_raw=b, swap_sold_raw=s,
                    swap_net_raw=b - s, transfer_in_raw=tm["transfer_in"], transfer_out_raw=tm["transfer_out"], burned_raw=tm["burned"], burn_ops=tm["burn_n"],
                    last_balance_raw=last_raw, account_closed=int(bool(cl)), rent_to=cl[2] if cl else "", decimals=decs.get(mt, ""), gap_raw=gap,
                    burned_equals_swap_net=int(tm["burned"] == b - s and b - s > 0), burn_fee_payer=" ".join(payers),
                    burn_payer_is_coin_creator=int(bool(payers) and creator_of.get(mt) in payers) if creator_of.get(mt) else "",
                    last_swap_utc=iso(slot_time[lastslot]) if lastslot in slot_time else "", burn_utc=iso(slot_time[bs]) if bs in slot_time else "",
                    swap_to_burn_s=(slot_time[bs] - slot_time[lastslot]) if bs in slot_time and lastslot in slot_time else ""))
wcsv("residual_positions.csv", pos)

# slot ties for first/last balance of each wallet
ties = {}
for w in NINE:
    lst = sorted([x for x in SIGS[w] if not x["err"]], key=lambda x: x["slot"])
    if not lst:
        continue
    fs, ls = lst[0]["slot"], lst[-1]["slot"]
    ties[w[:8]] = dict(first_slot_txs=sum(1 for x in lst if x["slot"] == fs), last_slot_txs=sum(1 for x in lst if x["slot"] == ls))

ps = [p for p in pos if p["swap_net_raw"] > 0]
res = dict(cosigned=len(cos), cosign_by_payer=dict(collections.Counter(r["fee_payer"][:8] for r in cos)), cosign_by_n=dict(sorted(collections.Counter(r["nine_signers"] for r in cos).items())),
           burns=sum(1 for e in ev if e["op"] == "burn"), closes=sum(1 for e in ev if e["op"] == "closeAccount"),
           burns_by_payer=dict(collections.Counter(e["fee_payer"][:8] for e in ev if e["op"] == "burn")),
           burns_in_own_tx=sum(1 for e in ev if e["op"] == "burn" and e["fee_payer"] in N),
           closes_rent_to=dict(collections.Counter((e["rent_destination"][:8] + (" (временный)" if "создан" in str(e["lamports_refunded"]) else "")) for e in ev if e["op"] == "closeAccount").most_common(12)),
           closes_rent_to_creators_sol=round(sum(int(e["lamports_refunded"]) for e in ev if e["op"] == "closeAccount" and e["rent_destination"] not in N and str(e["lamports_refunded"]).isdigit()) / 1e9, 6),
           rent_check_txs=len(rows), rent_unexplained_max=max(une) if une else None, rent_unexplained_nonzero=sum(1 for x in une if x > 1e-9),
           rent_unexplained_sum=round(sum(r["unexplained"] for r in rows), 9),
           positions=len(pos), positions_swap_net_positive=len(ps), burned_equals_swap_net=sum(p["burned_equals_swap_net"] for p in ps),
           positions_with_burn=sum(1 for p in ps if p["burned_raw"] > 0), positions_gap_zero=sum(1 for p in ps if p["gap_raw"] == 0),
           positions_still_held=sum(1 for p in ps if p["last_balance_raw"] > 0 and not p["burned_raw"]),
           transfers_out_positions=sum(1 for p in pos if p["transfer_out_raw"] > 0), transfers_in_positions=sum(1 for p in pos if p["transfer_in_raw"] > 0),
           burn_payer_is_coin_creator=dict(collections.Counter(str(p["burn_payer_is_coin_creator"]) for p in ps if p["burned_raw"] > 0)),
           swap_to_burn_s_median=statistics.median([p["swap_to_burn_s"] for p in ps if p["swap_to_burn_s"] != ""]) if any(p["swap_to_burn_s"] != "" for p in ps) else None,
           slot_ties=ties)
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
