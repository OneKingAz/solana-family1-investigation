"""Task 03 (analyst, 18.11): individual SOL routes of the park wallets that received SOL from the GEKKO creator. NO RPC; sources only read.
Sources: sol_export_transfers.csv (17.11 export: SOL / token transfers with signature, slot, blockTime), sol_export_balances.csv (the wallets
whose own history was downloaded = full history inside the export window), sol_buyers.csv (v2 roles: «парк»), sol_pools.csv /
sol_pool_rec.jsonl / sol_watch_paths.jsonl (known pool creators).
A «return to GEKKO» is a SOL transfer whose destination is exactly the GEKKO creator. Swaps (in_trade = True) are excluded.
Infrastructure = treasury, sponsor, GEKKO creator, other known pool creators. Transfers to other park wallets are counted separately.
Out: C:\\Users\\IT\\Desktop\\bsc_meme_bot\\investigation_task_03\\ park_wallet_flows.csv, park_flow_transactions.csv (+ numbers for the report)."""
import collections, csv, datetime as dt, json, os, sys

sys.stdout.reconfigure(encoding="utf-8")
A = os.path.dirname(os.path.abspath(__file__))
OUT = r"C:\Users\IT\Desktop\bsc_meme_bot\investigation_task_03"
os.makedirs(OUT, exist_ok=True)
TRE, SPO, GC = "B7StC42h126Hmtkw4GoRMcaHA5ZuKawfa9fCSTV6UMSj", "3azG8rmtPnNUz77a6UqBKt1ykpk3JQpLLNTaoXW31b34", "Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL"
X7 = "7hm4V7g2hfdmhaA2c6KLnnAoYsp8CvY8B5xYhCbNjppR"
iso = lambda u: dt.datetime.fromtimestamp(int(u), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if u not in (None, "") else ""
rd = lambda fn: list(csv.DictReader(open(os.path.join(A, fn), encoding="utf-8-sig"), delimiter=";"))

PARK = {r["who"] for r in rd("sol_buyers.csv") if r["role"] == "парк"}
creators = {r["creator"] for r in rd("sol_pools.csv")}
for fn in ("sol_pool_rec.jsonl", "sol_watch_paths.jsonl"):
    for l in open(os.path.join(A, fn), encoding="utf-8"):
        d = json.loads(l)
        if d.get("creator"):
            creators.add(d["creator"])
INFRA = {TRE: "казна", SPO: "спонсор", GC: "создатель GEKKO"}
for c in creators:
    INFRA.setdefault(c, "создатель пула " + c[:8])
FULL = {r[next(iter(r))] for r in rd("sol_export_balances.csv")}  # first column = wallet
T = [r for r in rd("sol_export_transfers.csv") if r["asset"] == "SOL" and r["in_trade"] != "True"]
WIN = (iso(min(int(r["blockTime"]) for r in T)), iso(max(int(r["blockTime"]) for r in T)))
W109 = sorted({r["destination"] for r in T if r["source"] == GC and r["destination"] in PARK})

rows, tx_rows = [], []
for w in W109:
    ins = [r for r in T if r["destination"] == w]
    outs = [r for r in T if r["source"] == w]
    def agg(xs):
        if not xs:
            return 0, 0.0, "", ""
        xs = sorted(xs, key=lambda r: int(r["slot"]))
        return len(xs), round(sum(float(r["amount"]) for r in xs), 6), iso(xs[0]["blockTime"]), iso(xs[-1]["blockTime"])
    g_in = [r for r in ins if r["source"] == GC]
    g_out = [r for r in outs if r["destination"] == GC]
    t_out = [r for r in outs if r["destination"] == TRE]
    s_out = [r for r in outs if r["destination"] == SPO]
    o_out = [r for r in outs if r["destination"] in INFRA and r["destination"] not in (GC, TRE, SPO)]
    p_out = [r for r in outs if r["destination"] in PARK]
    other_infra_in = [r for r in ins if r["source"] in INFRA and r["source"] != GC]
    row = dict(wallet=w, full_history_in_export=int(w in FULL))
    for name, xs in (("from_gekko", g_in), ("to_gekko", g_out), ("to_treasury", t_out), ("to_sponsor", s_out), ("to_other_infra", o_out), ("to_park", p_out),
                     ("from_other_infra", other_infra_in)):
        n, s, a, b = agg(xs)
        row[f"{name}_n"], row[f"{name}_sol"], row[f"{name}_first_utc"], row[f"{name}_last_utc"] = n, s, a, b
    row["to_other_infra_addresses"] = " ".join(sorted({r["destination"] for r in o_out}))
    row["total_in_sol"] = round(sum(float(r["amount"]) for r in ins), 6)
    row["total_out_sol"] = round(sum(float(r["amount"]) for r in outs), 6)
    row["balance_in_minus_out"] = round(row["total_in_sol"] - row["total_out_sol"], 6)  # all SOL transfers: includes wraps to own WSOL accounts (not flagged as trades)
    row["infra_balance"] = round(row["from_gekko_sol"] + row["from_other_infra_sol"] - row["to_gekko_sol"] - row["to_treasury_sol"] - row["to_sponsor_sol"] - row["to_other_infra_sol"], 6)
    row["returned_share"] = round(row["to_gekko_sol"] / row["from_gekko_sol"], 4) if row["from_gekko_sol"] else ""
    row["n_in_all"], row["n_out_all"] = len(ins), len(outs)
    infra_dest = {r["destination"] for r in outs if r["destination"] in INFRA}
    if not row["full_history_in_export"]:
        cls = "недостаточно_данных"
    elif g_out and (infra_dest - {GC}):
        cls = "получил_и_отправлял_нескольким_участникам"
    elif g_out:
        cls = "получил_и_вернул_GEKKO"
    elif infra_dest:
        cls = "получил_от_GEKKO_отправил_другому_инфраструктуры"
    else:
        cls = "получил_от_GEKKO_не_возвращал_GEKKO"
    row["class"] = cls
    rows.append(row)
    for r in g_in + g_out + t_out + s_out + o_out + other_infra_in + p_out:
        d = "от создателя GEKKO" if r in g_in else "возврат создателю GEKKO" if r in g_out else "казне" if r in t_out else "спонсору" if r in s_out else \
            "другому участнику инфраструктуры" if r in o_out else "от другого участника инфраструктуры" if r in other_infra_in else "другому кошельку парка"
        tx_rows.append(dict(wallet=w, direction=d, signature=r["signature"], slot=r["slot"], time_utc=iso(r["blockTime"]), source=r["source"],
                            source_role=INFRA.get(r["source"], "парк" if r["source"] in PARK else ""), destination=r["destination"],
                            destination_role=INFRA.get(r["destination"], "парк" if r["destination"] in PARK else ""), sol=r["amount"]))

with open(os.path.join(OUT, "park_wallet_flows.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(rows)
tx_rows.sort(key=lambda r: (r["wallet"], int(r["slot"])))
with open(os.path.join(OUT, "park_flow_transactions.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(tx_rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(tx_rows)

cls = collections.Counter(r["class"] for r in rows)
S = lambda k, sub=None: round(sum(r[k] for r in (sub or rows)), 2)
res = dict(n=len(rows), window=WIN, classes=dict(cls), full=sum(r["full_history_in_export"] for r in rows),
           from_gc=(sum(r["from_gekko_n"] for r in rows), S("from_gekko_sol")), to_gc=(sum(r["to_gekko_n"] for r in rows), S("to_gekko_sol")),
           to_tre=(sum(r["to_treasury_n"] for r in rows), S("to_treasury_sol")), to_spo=(sum(r["to_sponsor_n"] for r in rows), S("to_sponsor_sol")),
           to_oth=(sum(r["to_other_infra_n"] for r in rows), S("to_other_infra_sol")), to_park=(sum(r["to_park_n"] for r in rows), S("to_park_sol")),
           from_oth=(sum(r["from_other_infra_n"] for r in rows), S("from_other_infra_sol")),
           oth_addr=collections.Counter(a for r in rows for a in r["to_other_infra_addresses"].split()).most_common(10),
           balance_total=S("balance_in_minus_out"), infra_balance_total=S("infra_balance"), in_total=S("total_in_sol"), out_total=S("total_out_sol"),
           ratio_returned=[round(r["to_gekko_sol"] / r["from_gekko_sol"], 2) for r in rows if r["from_gekko_sol"]],
           x7=next((r for r in rows if r["wallet"] == X7), None), x7_tx=[t for t in tx_rows if t["wallet"] == X7], tx_n=len(tx_rows))
json.dump(res, open(os.path.join(OUT, "_numbers.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: v for k, v in res.items() if k not in ("ratio_returned", "x7_tx")}, ensure_ascii=False, indent=1, default=str))
import statistics as st
rr = res["ratio_returned"]
print("доля возврата (вернул/получил): медиана", st.median(rr), "; вернули >= 50%:", sum(x >= 0.5 for x in rr), "; 0:", sum(x == 0 for x in rr))
print("7hm4 транзакции:", [(t["direction"], t["time_utc"], t["sol"]) for t in res["x7_tx"]])
