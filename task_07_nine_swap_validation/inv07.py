"""Task 07 (analyst): validation of swap legs of the nine wallets from DECODED instructions, not from final balance changes.
Input: analysis/inv06_raw.jsonl.gz (+ missing signatures fetched here via Helius; HELIUS_KEY of D:\\bot\\.env, never printed).
Per tx (signed by one of the nine): every top-level PumpSwap / Meteora DAMM v2 instruction = one leg; its discriminator; pool, mints;
token transfers inside that instruction (meta.innerInstructions[index]) classified by account owner: user -> pool vault, pool vault ->
user, user -> other (fees). Side: WSOL into pool + coin out of pool = BUY coin; coin into pool + WSOL out = SELL coin.
Native SOL split: network fee (meta.fee), rent of accounts created by the wallet (system createAccount), wrap transfers to the wallet's
WSOL accounts, other system transfers, residual (= rent refunds of closed accounts + anything unexplained).
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_07\\ (see report)."""
import collections, csv, datetime as dt, gzip, json, os, sys, threading, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_07"
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
WSOL = "So11111111111111111111111111111111111111112"
SYS = "11111111111111111111111111111111"
START = int(dt.datetime(2026, 11, 17, 13, 30, tzinfo=dt.timezone.utc).timestamp())
DISC = {"33e685a4017f83ad": "pumpswap.sell(base_in)", "66063d1201daebea": "pumpswap.buy(base_out)", "c62e1552b4d9e870": "pumpswap.buy_exact_quote_in",
        "f8c69e91e17587c8": "meteora.swap", "414b3f4ceb5b5b88": "meteora.swap2"}
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b


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
                                                                         headers={"Content-Type": "application/json"}), timeout=60).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            pass
        time.sleep(1 + k)
    return None


rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))
NINE = [r["wallet"] for r in rd(r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_04\nine_wallets.csv")]
N = set(NINE)
creator_of = {r["mint"]: r["creator"] for r in rd(os.path.join(A, "sol_pools.csv"))}
for r in rd(os.path.join(A, "sol_watch.csv")) if os.path.exists(os.path.join(A, "sol_watch.csv")) else []:  # same sources as inv06b
    if r.get("mint") and r.get("creator"):
        creator_of.setdefault(r["mint"], r["creator"])
if os.path.exists(os.path.join(A, "sol_pool_rec.jsonl")):
    for l in open(os.path.join(A, "sol_pool_rec.jsonl"), encoding="utf-8"):
        try:
            d = json.loads(l)
        except Exception:
            continue
        if d.get("mint") and d.get("creator"):
            creator_of.setdefault(d["mint"], d["creator"])
CREATORS = set(creator_of.values())

# ---------- 1. signatures: per wallet list (same rule as inv06: blockTime >= START), errors kept separately ----------
RAW = os.path.join(A, "inv06_raw.jsonl.gz")
have = {}
with gzip.open(RAW, "rt", encoding="utf-8") as f:
    for l in f:
        d = json.loads(l)
        have[d["signature"]] = d["tx"]
SIGCACHE = os.path.join(A, "inv07_sigs.json")
if os.path.exists(SIGCACHE):
    siglists = json.load(open(SIGCACHE, encoding="utf-8"))
else:
    siglists = {}
    for w in NINE:
        out, before = [], None
        while True:
            p = {"limit": 1000}
            if before:
                p["before"] = before
            page = rpc("getSignaturesForAddress", [w, p]) or []
            out += page
            if len(page) < 1000 or (page and (page[-1].get("blockTime") or 0) < START):
                break
            before = page[-1]["signature"]
        siglists[w] = [dict(signature=s["signature"], slot=s["slot"], blockTime=s.get("blockTime"), err=bool(s.get("err"))) for s in out
                       if (s.get("blockTime") or 0) >= START]
    json.dump(siglists, open(SIGCACHE, "w", encoding="utf-8"))
recs = [(w, s) for w in NINE for s in siglists[w]]
ok_recs = [(w, s) for w, s in recs if not s["err"]]
uniq_ok = {s["signature"] for _, s in ok_recs}
missing0 = sorted(uniq_ok - set(have))
print(f"записей кошелёк-транзакция {len(recs)} (с ошибкой {len(recs) - len(ok_recs)}), уникальных успешных подписей {len(uniq_ok)}, "
      f"нет в выгрузке inv06 {len(missing0)}", flush=True)
lockw = threading.Lock()


def fetch(sig):
    t = rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if t:
        with lockw:
            with gzip.open(RAW, "at", encoding="utf-8") as f:
                f.write(json.dumps({"signature": sig, "tx": t}) + "\n")
            have[sig] = t


with ThreadPoolExecutor(6) as ex:
    list(ex.map(fetch, missing0))
still = sorted(uniq_ok - set(have))
with open(os.path.join(OUT, "missing_signatures.csv"), "w", newline="", encoding="utf-8-sig") as f:
    wr = csv.writer(f, delimiter=";")
    wr.writerow(["wallet", "signature", "slot", "blockTime", "status"])
    for w, s in recs:
        if s["err"]:
            wr.writerow([w, s["signature"], s["slot"], s["blockTime"], "транзакция с ошибкой в сети (не учитывается)"])
        elif s["signature"] in still:
            wr.writerow([w, s["signature"], s["slot"], s["blockTime"], "узел не отдал транзакцию"])
        elif s["signature"] in missing0:
            wr.writerow([w, s["signature"], s["slot"], s["blockTime"], "не было в inv06, докачана в inv07"])
multi = collections.Counter(s["signature"] for _, s in ok_recs)
print(f"докачано {len(missing0) - len(still)}, не получено {len(still)}; подписей в истории нескольких из девяти: "
      f"{sum(1 for v in multi.values() if v > 1)}", flush=True)

# ---------- 2. decode ----------
legs, txrows = [], []
extend_n = [0]
for sig in sorted(uniq_ok & set(have)):
    t = have[sig]
    m = t["meta"]
    msg = t["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    signer = keys[0]
    watched = [w for w in NINE if w in keys]
    tb = {}  # account -> (mint, owner, decimals)
    for b in (m.get("preTokenBalances") or []) + (m.get("postTokenBalances") or []):
        tb[keys[b["accountIndex"]]] = (b["mint"], b.get("owner"), b["uiTokenAmount"]["decimals"])
    inner = {g["index"]: g["instructions"] for g in m.get("innerInstructions") or []}
    # accounts that receive SOL from the signer via top-level system transfer and are then synced = signer's WSOL accounts
    wsol_accts = set()
    for ins in msg["instructions"]:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if isinstance(p, dict) and p.get("type") == "syncNative":
            wsol_accts.add(p["info"]["account"])
    # token accounts initialised inside the tx (temporary WSOL accounts are created and closed here, so they are not in token balances)
    for g, lst in inner.items():
        for ins in lst:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type") in ("initializeAccount", "initializeAccount2", "initializeAccount3"):
                inf = p["info"]
                if inf["account"] not in tb:
                    tb[inf["account"]] = (inf["mint"], inf.get("owner"), 9 if inf["mint"] == WSOL else None)
    for a, (mt, ow, dc) in tb.items():
        if mt == WSOL and ow == signer:
            wsol_accts.add(a)
    post_raw = {keys[b["accountIndex"]]: int(b["uiTokenAmount"]["amount"]) for b in m.get("postTokenBalances") or []}
    created = []  # (account, lamports) created and paid by signer (any depth)
    closed = []
    allins = [(i, ins, None) for i, ins in enumerate(msg["instructions"])] + [(g, ins, g) for g, lst in inner.items() for ins in lst]
    for i, ins, g in allins:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if not isinstance(p, dict):
            continue
        inf = p.get("info", {})
        if ins.get("program") == "system" and p.get("type") in ("createAccount", "createAccountWithSeed") and inf.get("source") == signer:
            created.append((inf["newAccount"], int(inf["lamports"]) / 1e9))
        if p.get("type") == "closeAccount" and inf.get("destination") == signer:
            closed.append(inf["account"])
    # native SOL split
    wrap = other_out = other_in = 0.0
    other_detail = []
    for i, ins, g in allins:
        p = ins.get("parsed") if isinstance(ins, dict) else None
        if not (isinstance(p, dict) and ins.get("program") == "system" and p.get("type") == "transfer"):
            continue
        inf = p["info"]
        v = int(inf["lamports"]) / 1e9
        if inf["source"] == signer and inf["destination"] in wsol_accts:
            wrap += v
        elif inf["source"] == signer:
            other_out += v
            other_detail.append(f"->{inf['destination'][:8]}:{v:g}")
        elif inf["destination"] == signer:
            other_in += v
            other_detail.append(f"<-{inf['source'][:8]}:{v:g}")
    si = keys.index(signer)
    d_native = (m["postBalances"][si] - m["preBalances"][si]) / 1e9
    fee = m["fee"] / 1e9 if True else 0
    rent_paid = sum(v for _, v in created)
    # ---- legs ----
    tx_legs = []
    for i, ins in enumerate(msg["instructions"]):
        pid = ins.get("programId")
        if pid not in (AMM, MET) or "data" not in ins:
            continue
        raw = b58dec(ins["data"])
        disc = raw[:8].hex()
        if disc == "ea66c2cb96483ee5":  # PumpSwap ExtendAccount (pool account resize, rent paid to the pool) — not a swap; its SOL is in other_sol_out
            extend_n[0] += 1
            continue
        accs = ins.get("accounts", [])
        pool = accs[0] if pid == AMM else (accs[1] if len(accs) > 1 else "")
        vault_owners = {accs[0]}  # PumpSwap: pool owns its vaults; Meteora DAMM v2: accounts[0] = pool authority owns the vaults
        flows = collections.defaultdict(int)  # (direction, mint) -> raw amount
        dec = {}
        fee_tr = collections.defaultdict(int)
        unknown = 0
        for ins2 in inner.get(i, []):
            p = ins2.get("parsed") if isinstance(ins2, dict) else None
            if not (isinstance(p, dict) and p.get("type") in ("transfer", "transferChecked") and ins2.get("program") in ("spl-token", "spl-token-2022")):
                continue
            inf = p["info"]
            src, dst = inf["source"], inf["destination"]
            if p["type"] == "transferChecked":
                mint, amt, dcm = inf["mint"], int(inf["tokenAmount"]["amount"]), inf["tokenAmount"]["decimals"]
            else:
                amt = int(inf["amount"])
                info = tb.get(src) or tb.get(dst)
                if src in wsol_accts or dst in wsol_accts:
                    mint, dcm = WSOL, 9
                elif info:
                    mint, dcm = info[0], info[2]
                else:
                    unknown += 1
                    continue
            dec[mint] = dcm
            src_pool = tb.get(src, (None, None))[1] in vault_owners
            dst_pool = tb.get(dst, (None, None))[1] in vault_owners
            auth = inf.get("authority") or inf.get("multisigAuthority")
            if auth == signer and dst_pool:
                flows[("to_pool", mint)] += amt
            elif src_pool and not dst_pool and (dst in wsol_accts or tb.get(dst, (None, None))[1] == signer):
                flows[("from_pool", mint)] += amt
            elif auth == signer:
                fee_tr[mint] += amt
            elif src_pool:
                fee_tr[("pool_out_other", mint)] += amt  # e.g. protocol fee paid from the vault
        mints = {mt for (_, mt) in flows}
        coin = next((mt for mt in mints if mt != WSOL), None)
        w_in, w_out = flows[("to_pool", WSOL)] / 1e9, flows[("from_pool", WSOL)] / 1e9
        c_in = flows[("to_pool", coin)] / 10 ** dec.get(coin, 0) if coin else 0
        c_out = flows[("from_pool", coin)] / 10 ** dec.get(coin, 0) if coin else 0
        side = "BUY" if (w_in > 0 and c_out > 0 and c_in == 0 and w_out == 0) else "SELL" if (c_in > 0 and w_out > 0 and w_in == 0 and c_out == 0) else "UNCLEAR"
        fee_wsol = fee_tr.get(WSOL, 0) / 1e9  # paid by the user from its WSOL account (affects its native SOL)
        fee_vault_wsol = fee_tr.get(("pool_out_other", WSOL), 0) / 1e9  # paid by the pool vault to fee recipients
        fee_coin_raw = (fee_tr.get(coin, 0) + fee_tr.get(("pool_out_other", coin), 0)) if coin else 0
        fee_coin = fee_coin_raw / 10 ** dec.get(coin, 0) if coin else 0
        # coin fee valued at this leg's own price (WSOL per coin)
        px = (w_in / c_out) if side == "BUY" and c_out else (w_out / c_in) if side == "SELL" and c_in else 0
        user_coin_acct = next((a for a, v in tb.items() if v[0] == coin and v[1] == signer), None) if coin else None
        leg = dict(signature=sig, slot=t["slot"], blockTime=t["blockTime"], time_utc=iso(t["blockTime"]), signer=signer, leg_index=len(tx_legs) + 1, ix_index=i,
                   program="PumpSwap" if pid == AMM else "Meteora DAMM v2", program_id=pid, discriminator=disc, instruction=DISC.get(disc, "неизвестна"),
                   pool=pool, mint=coin or "", side=side, wsol_to_pool=round(w_in, 9), wsol_from_pool=round(w_out, 9), coin_to_pool=c_in, coin_from_pool=c_out,
                   wsol_to_pool_raw=flows[("to_pool", WSOL)], wsol_from_pool_raw=flows[("from_pool", WSOL)],
                   coin_to_pool_raw=flows[("to_pool", coin)] if coin else 0, coin_from_pool_raw=flows[("from_pool", coin)] if coin else 0, coin_decimals=dec.get(coin, ""),
                   fee_from_user_wsol=round(fee_wsol, 9), fee_from_vault_wsol=round(fee_vault_wsol, 9), fee_from_user_coin=fee_coin, fee_coin_raw=fee_coin_raw, fee_coin_in_sol=round(fee_coin * px, 9),
                   user_coin_account=user_coin_acct or "", coin_balance_after_tx_raw=post_raw.get(user_coin_acct, "") if user_coin_acct else "",
                   temp_wsol_accounts=" ".join(sorted(wsol_accts)),
                   unparsed_transfers=unknown, creator=creator_of.get(coin, "") if coin else "")
        tx_legs.append(leg)
    legs += tx_legs
    n_amm = sum(1 for l in tx_legs if l["program"] == "PumpSwap")
    n_met = sum(1 for l in tx_legs if l["program"] != "PumpSwap")
    sides = "+".join(l["side"] for l in tx_legs)
    same_pool = int(len({l["pool"] for l in tx_legs}) == 1) if tx_legs else ""
    same_mint = int(len({l["mint"] for l in tx_legs}) == 1) if tx_legs else ""
    pattern = ("BUY→SELL" if [l["side"] for l in tx_legs] == ["BUY", "SELL"] else "SELL→BUY" if [l["side"] for l in tx_legs] == ["SELL", "BUY"] else sides or "нет обменов")
    wsol_net_to_pool = sum(l["wsol_to_pool"] - l["wsol_from_pool"] for l in tx_legs)
    coin_net = sum(l["coin_from_pool"] - l["coin_to_pool"] for l in tx_legs)
    fee_w = sum(l["fee_from_user_wsol"] for l in tx_legs)
    # residual = what native change is not explained by fee, rent paid, WSOL into pools (net), DEX fees in WSOL, other transfers
    explained = -fee - rent_paid - wsol_net_to_pool - fee_w - other_out + other_in
    residual = d_native - explained
    venue = "PumpSwap" if n_amm and not n_met else "Meteora DAMM v2" if n_met and not n_amm else "обе" if n_amm else "без обмена"
    txrows.append(dict(signature=sig, slot=t["slot"], blockTime=t["blockTime"], time_utc=iso(t["blockTime"]), signer=signer, signer_is_nine=int(signer in N),
                       watched_wallets=" ".join(w[:8] for w in watched), venue=venue, legs_pumpswap=n_amm, legs_meteora=n_met, pattern=pattern,
                       same_pool=same_pool, same_mint=same_mint, mint=tx_legs[0]["mint"] if tx_legs else "",
                       wsol_to_pool=round(sum(l["wsol_to_pool"] for l in tx_legs), 9), wsol_from_pool=round(sum(l["wsol_from_pool"] for l in tx_legs), 9),
                       coin_bought=sum(l["coin_from_pool"] for l in tx_legs), coin_sold=sum(l["coin_to_pool"] for l in tx_legs), coin_net=coin_net,
                       dex_fee_wsol=round(fee_w, 9), dex_fee_vault_wsol=round(sum(l["fee_from_vault_wsol"] for l in tx_legs), 9),
                       dex_fee_coin=sum(l["fee_from_user_coin"] for l in tx_legs), dex_fee_coin_in_sol=round(sum(l["fee_coin_in_sol"] for l in tx_legs), 9),
                       coin_balance_after_tx_raw=tx_legs[-1]["coin_balance_after_tx_raw"] if tx_legs else "", network_fee=fee, rent_paid=round(rent_paid, 9),
                       accounts_created=len(created), accounts_closed_to_signer=len(closed), wrap_to_wsol=round(wrap, 9), other_sol_out=round(other_out, 9),
                       other_sol_in=round(other_in, 9), other_sol_detail=" ".join(other_detail[:6]), native_change=round(d_native, 9),
                       residual_rent_refund_and_unexplained=round(residual, 9), unparsed_transfers=sum(l["unparsed_transfers"] for l in tx_legs)))


def wcsv(name, rows):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
        wr.writeheader()
        wr.writerows(rows)


wcsv("nine_swap_legs.csv", legs)
wcsv("nine_tx_validation.csv", txrows)

# ---------- 3. per coin ----------
coin = collections.defaultdict(lambda: dict(buy_legs=0, sell_legs=0, wsol_in=0.0, wsol_out=0.0, tok_bought=0.0, tok_sold=0.0, fee_w=0.0, pools=set(), first={},
                                            venues=set()))
for l in legs:
    if not l["mint"] or l["signer"] not in N:
        continue
    c = coin[l["mint"]]
    c["buy_legs"] += l["side"] == "BUY"
    c["sell_legs"] += l["side"] == "SELL"
    c["wsol_in"] += l["wsol_to_pool"]
    c["wsol_out"] += l["wsol_from_pool"]
    c["tok_bought"] += l["coin_from_pool"]
    c["tok_sold"] += l["coin_to_pool"]
    c["fee_w"] += l["fee_from_user_wsol"]
    c["pools"].add(l["pool"])
    c["venues"].add(l["program"])
    if l["side"] == "BUY":
        c["first"].setdefault(l["signer"], (l["slot"], l["blockTime"]))
        if l["slot"] < c["first"][l["signer"]][0]:
            c["first"][l["signer"]] = (l["slot"], l["blockTime"])
crows = []
for mt, c in coin.items():
    order = sorted(c["first"].items(), key=lambda kv: kv[1][0])
    crows.append(dict(mint=mt, creator=creator_of.get(mt, ""), pools=" ".join(sorted(c["pools"])), venues=" ".join(sorted(c["venues"])), wallets_bought=len(order),
                      first_buy_order=" ".join(w[:6] for w, _ in order), first_buy_utc=iso(order[0][1][1]) if order else "",
                      last_wallet_first_buy_utc=iso(order[-1][1][1]) if order else "", interval_first_to_last_wallet_s=(order[-1][1][1] - order[0][1][1]) if order else "",
                      buy_legs=c["buy_legs"], sell_legs=c["sell_legs"], gross_buy_sol=round(c["wsol_in"], 6), gross_sell_sol=round(c["wsol_out"], 6),
                      tokens_bought=c["tok_bought"], tokens_sold=c["tok_sold"], net_tokens=c["tok_bought"] - c["tok_sold"],
                      net_sol_to_pools=round(c["wsol_in"] - c["wsol_out"], 6), dex_fee_wsol=round(c["fee_w"], 6)))
crows.sort(key=lambda r: -r["net_sol_to_pools"])
wcsv("nine_coin_net_positions.csv", crows)

# ---------- 4. balance reconciliation per wallet ----------
rec = []
for w in NINE:
    mine = sorted([r for r in txrows if w in [x for x in NINE if x[:8] in r["watched_wallets"].split()]], key=lambda r: (r["slot"], r["signature"]))
    first_pre = last_post = None
    tin = collections.Counter()
    tout = collections.Counter()
    nat_signed = nat_other = 0.0
    for r in mine:
        t = have[r["signature"]]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in t["transaction"]["message"]["accountKeys"]]
        i = keys.index(w)
        if first_pre is None:
            first_pre = t["meta"]["preBalances"][i] / 1e9
        last_post = t["meta"]["postBalances"][i] / 1e9
        dn = (t["meta"]["postBalances"][i] - t["meta"]["preBalances"][i]) / 1e9
        if r["signer"] == w:
            nat_signed += dn
        else:
            nat_other += dn
    S = [r for r in mine if r["signer"] == w]
    g = lambda k: round(sum(r[k] for r in S), 6)
    rec.append(dict(wallet=w, txs=len(mine), signed_by_wallet=len(S), sol_at_window_start=round(first_pre, 6), sol_at_last_tx=round(last_post, 6),
                    native_change_total=round(last_post - first_pre, 6), native_change_in_txs_signed_by_others=round(nat_other, 6),
                    native_change_in_own_txs=round(nat_signed, 6), received_from_others=g("other_sol_in"), sent_direct=g("other_sol_out"),
                    wsol_net_to_pumpswap=round(sum(r["wsol_to_pool"] - r["wsol_from_pool"] for r in S if r["venue"] == "PumpSwap"), 6),
                    wsol_net_to_meteora=round(sum(r["wsol_to_pool"] - r["wsol_from_pool"] for r in S if r["venue"] == "Meteora DAMM v2"), 6),
                    dex_fee_wsol=g("dex_fee_wsol"), network_fee=g("network_fee"), rent_paid=g("rent_paid"), residual_rent_refund_and_unexplained=g("residual_rent_refund_and_unexplained"),
                    check_own=round(nat_signed - (g("other_sol_in") - g("other_sol_out") - sum(r["wsol_to_pool"] - r["wsol_from_pool"] for r in S) - g("dex_fee_wsol")
                                                  - g("network_fee") - g("rent_paid") + g("residual_rent_refund_and_unexplained")), 9)))
wcsv("nine_balance_reconciliation.csv", rec)

# ---------- 5. summary ----------
def stat(rows):
    return dict(txs=len(rows), patterns=dict(collections.Counter(r["pattern"] for r in rows).most_common(8)),
                legs=dict(collections.Counter(f"{r['legs_pumpswap']}+{r['legs_meteora']}" for r in rows).most_common(6)),
                same_pool=sum(1 for r in rows if r["same_pool"] == 1), same_mint=sum(1 for r in rows if r["same_mint"] == 1),
                wsol_to_pool=round(sum(r["wsol_to_pool"] for r in rows), 3), wsol_from_pool=round(sum(r["wsol_from_pool"] for r in rows), 3),
                wsol_net=round(sum(r["wsol_to_pool"] - r["wsol_from_pool"] for r in rows), 3), dex_fee_wsol=round(sum(r["dex_fee_wsol"] for r in rows), 4),
                network_fee=round(sum(r["network_fee"] for r in rows), 4), rent_paid=round(sum(r["rent_paid"] for r in rows), 4),
                residual=round(sum(r["residual_rent_refund_and_unexplained"] for r in rows), 4), coin_net_positive=sum(1 for r in rows if r["coin_net"] > 0),
                coin_net_negative=sum(1 for r in rows if r["coin_net"] < 0), unparsed=sum(r["unparsed_transfers"] for r in rows),
                native_change=round(sum(r["native_change"] for r in rows), 3))


own = [r for r in txrows if r["signer_is_nine"]]
res = dict(records_wallet_tx=len(recs), records_err=len(recs) - len(ok_recs), unique_ok_signatures=len(uniq_ok), in_several_histories=sum(1 for v in multi.values() if v > 1),
           fetched_now=len(missing0) - len(still), not_received=len(still), decoded=len(txrows), signed_by_nine=len(own), signed_by_others=len(txrows) - len(own),
           others_signers=dict(collections.Counter(r["signer"] for r in txrows if not r["signer_is_nine"]).most_common(10)),
           pumpswap=stat([r for r in own if r["venue"] == "PumpSwap"]), meteora=stat([r for r in own if r["venue"] == "Meteora DAMM v2"]),
           both=len([r for r in own if r["venue"] == "обе"]), no_swap=stat([r for r in own if r["venue"] == "без обмена"]),
           discriminators=dict(collections.Counter((l["program"], l["discriminator"], l["instruction"]) for l in legs if l["signer"] in N).most_common()),
           extend_account_instructions=extend_n[0], coins=len(crows), coins_all_nine=sum(1 for r in crows if r["wallets_bought"] == 9), calls=CALLS[0])
res["discriminators"] = {" | ".join(k): v for k, v in res["discriminators"].items()}
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
for r in rec:
    print(r)
