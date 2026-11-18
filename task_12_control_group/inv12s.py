"""Task 12 — final analysis by pool-size stratum (no RPC). Data: analysis/inv12_raw.jsonl.gz (6 random pools <= 5000 tx in full + 3 random large
pools, oldest 2500 tx) and analysis/inv05_raw.jsonl.gz (pool ErVpTsjX in full). Strata by the number of the pool's tx up to the nine's last trade:
small < 2500, medium 2500-5000, large > 5000 (ErVpTsjX full; 3 large pools — only their first 2500 tx, i.e. the entry window).
Same leg decoder and groups as inv12.py. Out: investigation_task_12/ control_groups_by_stratum.csv, control_wallets.csv, pools.csv, _numbers.json"""
import collections, csv, gzip, json, os, statistics, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
D = r"C:\Users\IT\Desktop\bsc_meme_bot"
OUT = os.path.join(D, "investigation_task_12")
os.makedirs(OUT, exist_ok=True)
AMM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
MET = "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG"
WSOL = "So11111111111111111111111111111111111111112"
B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
rd = lambda p: list(csv.DictReader(open(p, encoding="utf-8-sig"), delimiter=";"))


def b58dec(s):
    n = 0
    for c in s:
        n = n * 58 + B58.index(c)
    b = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    return b"\0" * (len(s) - len(s.lstrip("1"))) + b


NINE = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_04\nine_wallets.csv"))}
FLEET = {r["wallet"] for r in rd(os.path.join(D, r"investigation_task_03\park_wallet_flows.csv"))} - NINE
CRE = {r["pool_init_payer"] for r in rd(os.path.join(D, r"investigation_task_11\v2\pool_creator_fields.csv")) if r["pool_init_payer"]} | \
      {r["pool_field_creator"] for r in rd(os.path.join(D, r"investigation_task_11\v2\pool_creator_fields.csv")) if r["pool_field_creator"]}
ERVP = "EV5nTWTsmpq6HuLCzpqVSyqSSwMPLFX9cU59WTou5wvD"
n12 = json.load(open(os.path.join(OUT, "_numbers.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUT, "_numbers.json")) else {}
pool_tx = dict(n12.get("pool_tx", {}))
L = json.load(open(os.path.join(A, "inv12L_pools.json"), encoding="utf-8")) if os.path.exists(os.path.join(A, "inv12L_pools.json")) else {}
pool_tx.update({m: v["total_tx"] for m, v in L.items()})
pool_tx[ERVP] = 10297
stratum = {m: ("крупные (>5000)" if n > 5000 else "средние (2500–5000)" if n >= 2500 else "малые (<2500)") for m, n in pool_tx.items()}

txs = []
seen = set()
with gzip.open(os.path.join(A, "inv12_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        if d["signature"] in seen or d["mint"] not in stratum:
            continue
        seen.add(d["signature"])
        txs.append((d["mint"], d["tx"]))
with gzip.open(os.path.join(A, "inv05_raw.jsonl.gz"), "rt", encoding="utf-8") as f:
    for line in f:
        d = json.loads(line)
        txs.append((ERVP, d["tx"]))
# analyst: ErVpTsjX is the studied pool, not a control — it is reported as its own stratum and excluded from "все контрольные"
stratum[ERVP] = "исследуемый ErVpTsjX"


def decode(t):
    m = t["meta"]
    if m.get("err"):
        return None, []
    msg = t["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    signer = keys[0]
    tb = {}
    for b in (m.get("preTokenBalances") or []) + (m.get("postTokenBalances") or []):
        tb[keys[b["accountIndex"]]] = (b["mint"], b.get("owner"))
    inner = {g["index"]: g["instructions"] for g in m.get("innerInstructions") or []}
    for g in inner.values():
        for ins in g:
            p = ins.get("parsed") if isinstance(ins, dict) else None
            if isinstance(p, dict) and p.get("type", "").startswith("initializeAccount"):
                tb.setdefault(p["info"]["account"], (p["info"]["mint"], p["info"].get("owner")))
    out = []
    for i, ins in enumerate(msg["instructions"]):
        pid = ins.get("programId")
        if pid not in (AMM, MET) or "data" not in ins:
            continue
        raw = b58dec(ins["data"])
        if raw[:8].hex() == "ea66c2cb96483ee5":
            continue
        owner_pool = ins.get("accounts", [""])[0]
        fl = collections.Counter()
        for x in inner.get(i, []):
            p = x.get("parsed") if isinstance(x, dict) else None
            if not (isinstance(p, dict) and p.get("type") in ("transfer", "transferChecked") and x.get("program") in ("spl-token", "spl-token-2022")):
                continue
            inf = p["info"]
            src, dst = inf["source"], inf["destination"]
            amt = int(inf["tokenAmount"]["amount"]) if "tokenAmount" in inf else int(inf["amount"])
            mint = inf.get("mint") or (tb.get(src) or tb.get(dst) or ("?",))[0]
            sp, dp = tb.get(src, (None, None))[1] == owner_pool, tb.get(dst, (None, None))[1] == owner_pool
            auth = inf.get("authority")
            if auth == signer and dp:
                fl[("in", mint == WSOL)] += amt
            elif sp and tb.get(dst, (None, None))[1] == signer:
                fl[("out", mint == WSOL)] += amt
            elif auth == signer and not dp:
                fl[("fee", mint == WSOL)] += amt
        wi, co, ci, wo = fl[("in", True)], fl[("out", False)], fl[("in", False)], fl[("out", True)]
        side = "BUY" if wi and co else "SELL" if ci and wo else "?"
        vals = [int.from_bytes(raw[8 + 8 * k:16 + 8 * k], "little") for k in range((len(raw) - 8) // 8)]
        out.append(dict(side=side, wsol_in=wi / 1e9, coin_in=ci + fl[("fee", False)], coin_out=co, args=vals[:2], program="PumpSwap" if pid == AMM else "Meteora"))
    return signer, out


created = {}
per = collections.defaultdict(lambda: collections.defaultdict(lambda: dict(txs=0, buy=0, sell=0, rt=0, buys=[], kept=[], meq=0, rtp=0, first=None, cos=0)))
for mt, t in txs:
    signer, lg = decode(t)
    if not signer:
        continue
    signers = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"] if isinstance(k, dict) and k.get("signer")]
    cosigned = len(signers) > 1 and any(s in CRE for s in signers) and any(s not in CRE for s in signers)
    logs = " ".join(t["meta"].get("logMessages") or [])
    if "CreatePool" in logs or ("initialize" in logs.lower() and "pool" in logs.lower()):
        created[mt] = min(created.get(mt, 10 ** 12), t["blockTime"])
    if not lg:
        continue
    s = per[signer][mt]
    s["txs"] += 1
    s["cos"] += cosigned
    sides = [l["side"] for l in lg]
    s["buy"] += sides.count("BUY")
    s["sell"] += sides.count("SELL")
    for l in lg:
        if l["side"] == "BUY":
            s["buys"].append(l["wsol_in"])
            s["first"] = t["blockTime"] if s["first"] is None else min(s["first"], t["blockTime"])
    if sides[:2] == ["BUY", "SELL"]:
        s["rt"] += 1
        b, se = lg[0], lg[1]
        if b["coin_out"]:
            s["kept"].append(100 * (b["coin_out"] - se["coin_in"]) / b["coin_out"])
        if b["program"] == "PumpSwap":
            s["rtp"] += 1
            if len(b["args"]) > 1 and se["args"] and b["args"][1] == se["args"][0]:
                s["meq"] += 1


def group(w, allpools):
    if w in NINE:
        return "девять"
    if w in FLEET:
        return "парк-100"
    if w in CRE:
        return "создатели пулов"
    b = [x for s in allpools.values() for x in s["buys"]]
    if b and statistics.median(b) < 0.01:
        return "пыль (покупка < 0.01 SOL)"
    return "прочие"


GROUPS = ("девять", "парк-100", "создатели пулов", "прочие", "пыль (покупка < 0.01 SOL)")
STRATA = ("малые (<2500)", "средние (2500–5000)", "крупные (>5000)", "все контрольные", "исследуемый ErVpTsjX")
agg = collections.defaultdict(lambda: dict(wallets=set(), txs=0, buy=0, sell=0, rt=0, buys=[], kept=[], meq=0, rtp=0, entry=[], multi=set(), cos=0))
wrows = []
for w, pools in per.items():
    g = group(w, pools)
    for mt, s in pools.items():
        for st in (stratum.get(mt, "?"),) + (("все контрольные",) if mt != ERVP else ()):
            a = agg[(g, st)]
            a["cos"] += s["cos"]
            a["wallets"].add(w)
            a["txs"] += s["txs"]
            a["buy"] += s["buy"]
            a["sell"] += s["sell"]
            a["rt"] += s["rt"]
            a["buys"] += s["buys"]
            a["kept"] += s["kept"]
            a["meq"] += s["meq"]
            a["rtp"] += s["rtp"]
            if s["first"] and mt in created:
                a["entry"].append(s["first"] - created[mt])
            if len(pools) >= 2:
                a["multi"].add(w)
    wrows.append(dict(wallet=w, group=g, pools=len(pools), txs=sum(s["txs"] for s in pools.values()), roundtrip_txs=sum(s["rt"] for s in pools.values()),
                      minout_eq_sell=sum(s["meq"] for s in pools.values()), buy_sol_median=round(statistics.median([x for s in pools.values() for x in s["buys"]]), 6)
                      if any(s["buys"] for s in pools.values()) else ""))
rows = []
for st in STRATA:
    for g in GROUPS:
        a = agg.get((g, st))
        if not a or not a["wallets"]:
            continue
        rows.append(dict(stratum=st, group=g, wallets=len(a["wallets"]), wallets_in_2plus_pools=len(a["multi"]), txs=a["txs"], buy_legs=a["buy"], sell_legs=a["sell"],
                         roundtrip_txs=a["rt"], roundtrip_share=round(a["rt"] / a["txs"], 4) if a["txs"] else 0,
                         minout_equals_sell=f"{a['meq']}/{a['rtp']}", minout_equals_sell_share=round(a["meq"] / a["txs"], 4) if a["txs"] else 0,
                         cosigned_with_pool_creator=a["cos"], cosigned_share=round(a["cos"] / a["txs"], 4) if a["txs"] else 0,
                         burned_leftovers="не измеряется по транзакциям пула (сжигание идёт отдельными транзакциями)", buy_sol_median=round(statistics.median(a["buys"]), 6) if a["buys"] else "",
                         buy_sol_p90=round(sorted(a["buys"])[int(.9 * len(a["buys"]))], 6) if a["buys"] else "",
                         kept_pct_median=round(statistics.median(a["kept"]), 4) if a["kept"] else "",
                         entry_after_create_s_median=statistics.median(a["entry"]) if a["entry"] else ""))


def wcsv(name, rs):
    with open(os.path.join(OUT, name), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rs[0].keys()), delimiter=";")
        w.writeheader()
        w.writerows(rs)


wcsv("control_groups_by_stratum.csv", rows)
wcsv("control_wallets.csv", sorted(wrows, key=lambda r: (r["group"], -r["txs"])))
prow = [dict(mint=m, stratum=stratum[m], pool_tx_to_nine_last_trade=pool_tx[m], tx_analysed=sum(1 for mt, _ in txs if mt == m),
             window=(L[m].get("sampling", "2500 транзакций") if m in L else "полностью"), role="исследуемый" if m == ERVP else "контроль") for m in pool_tx]
wcsv("pools.csv", prow)
others_rt = sorted([r for r in wrows if r["group"] != "девять" and r["minout_eq_sell"] >= 5], key=lambda r: -r["minout_eq_sell"])
json.dump(dict(pools=prow, groups=rows, other_wallets_with_minout_eq_sell_5plus=others_rt[:50]), open(os.path.join(OUT, "_numbers_strata.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for r in rows:
    print(r)
print("кроме девяти, кошельков с ≥5 транзакциями «покупка → продажа ровно минимального выхода»:", len(others_rt))
for r in others_rt[:15]:
    print("  ", r)
