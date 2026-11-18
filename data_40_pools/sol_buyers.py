"""18.11 (user: «их боты реагируют на сумму покупки»). Does the farm withdraw the liquidity right after a BIG buy?
For every pool recorded by sol_pool_rec.py (sol_pool_rec.jsonl) and sol_watch.py (sol_watch_paths.jsonl): its transactions of the first
MAX_S seconds (public Solana node first, Helius if it fails), every swap: time from the pool's creation, signer, SOL into / out of the pool
(the pool's WSOL vault balance change), and the Withdraw. Then:
  - pools withdrawn early (< EARLY_S): the buys of the 15 s before the withdraw, the biggest one, by whom;
  - pools not withdrawn early: the biggest buy in their first EARLY_S seconds (did big buys happen there without a withdraw?);
  - a buy-size table: buys >= X SOL -> how often a withdraw follows within 15 s.
Roles (v2, same as sol_matrix.py): «парк» >= 0.05 SOL in 3+ pools, «пыль-маркер» 3+ pools all < 0.001 SOL, «мелкий повторяющийся», «посторонний», «МЫ».
Out: analysis/sol_buyers.txt, sol_buyers.csv.  Usage: python sol_buyers.py [max seconds per pool=120] [early=60]"""
import collections, csv, json, os, sys, time, urllib.request

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
MAX_S = float(sys.argv[1]) if len(sys.argv) > 1 else 120
EARLY_S = float(sys.argv[2]) if len(sys.argv) > 2 else 60
WSOL, ME = "So11111111111111111111111111111111111111112", "CqMsFPRFuSqCuxuK79kpw7cFm5ud8MoWBnqT27VfDx6J"
PUB = "https://api.mainnet-beta.solana.com"
K = [l.split("=", 1)[1].strip().strip('"\'') for l in open(r"D:\bot\.env", encoding="utf-8-sig") if l.strip().startswith("HELIUS_KEY=")][0]
HEL = "https://mainnet.helius-rpc.com/?api-key=" + K
CALLS = collections.Counter()


def rpc(m, p):
    for url, name in ((HEL, "helius"), (HEL, "helius"), (PUB, "public")):  # 18.11: the public node was far too slow (1 pool in 30 min)
        try:
            CALLS[name] += 1
            r = json.loads(urllib.request.urlopen(urllib.request.Request(url, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": m, "params": p}).encode(),
                                                                         headers={"Content-Type": "application/json"}), timeout=30).read())
            if r.get("result") is not None:
                return r["result"]
        except Exception:
            time.sleep(1.5)
    return None


pools = {}
for fn in ("sol_pool_rec.jsonl", "sol_watch_paths.jsonl"):
    try:
        for l in open(os.path.join(HERE, fn), encoding="utf-8"):
            d = json.loads(l)
            pools.setdefault(d["pool"], d)
    except OSError:
        pass
print(f"пулов: {len(pools)}", flush=True)

rows, per_pool = [], {}
for i, (pool, d) in enumerate(pools.items()):
    sigs, before = [], None
    while True:
        p = {"limit": 1000}
        if before:
            p["before"] = before
        page = rpc("getSignaturesForAddress", [pool, p]) or []
        sigs += page
        if len(page) < 1000:
            break
        before = page[-1]["signature"]
    sigs = [s for s in reversed(sigs) if s.get("blockTime")]
    if not sigs:
        continue
    t0 = sigs[0]["blockTime"]
    ev, wd = [], None
    for s in sigs:
        if s["blockTime"] - t0 > MAX_S:
            break
        if s.get("err"):
            continue
        t = rpc("getTransaction", [s["signature"], {"encoding": "json", "maxSupportedTransactionVersion": 0}])
        if not t or not t.get("meta"):
            continue
        m = t["meta"]
        la = m.get("loadedAddresses") or {}
        keys = t["transaction"]["message"]["accountKeys"] + la.get("writable", []) + la.get("readonly", [])
        signer = keys[0]
        pre = {b["accountIndex"]: float(b["uiTokenAmount"]["uiAmount"] or 0) for b in m.get("preTokenBalances") or [] if b.get("owner") == pool and b["mint"] == WSOL}
        post = {b["accountIndex"]: float(b["uiTokenAmount"]["uiAmount"] or 0) for b in m.get("postTokenBalances") or [] if b.get("owner") == pool and b["mint"] == WSOL}
        dsol = sum(post.values()) - sum(pre.values())
        logs = " ".join(m.get("logMessages") or [])
        tt = s["blockTime"] - t0
        if "Instruction: Withdraw" in logs:
            wd = tt
            ev.append((tt, signer, dsol, "withdraw", None))
            break
        if "CreatePool" in logs:
            continue
        if abs(dsol) > 1e-6:
            pre_sol = (m.get("preBalances") or [0])[0] / 1e9  # the signer's SOL before this tx: ~= the buy = funded just for it
            ev.append((tt, signer, dsol, "buy" if dsol > 0 else "sell", round(pre_sol, 6)))
    per_pool[pool] = dict(t0=t0, wd=wd, ev=ev, creator=d.get("creator"))
    print(f"{i + 1}/{len(pools)} {pool[:8]}: событий {len(ev)}, вывод {wd}", flush=True)

# repeat wallets
# v2 (analyst 18.11): the same roles as sol_matrix.py: «парк» = bought >= 0.05 SOL in 3+ pools; «пыль-маркер» = bought in 3+ pools and
# never more than 0.001 SOL; «мелкий повторяющийся» = 3+ pools, the rest; «посторонний» = fewer than 3 pools. v1: any 3+ pools = «бот фермы» (667)
seen_in, big_in, max_buy = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(float)
for pool, pp in per_pool.items():
    for tt, who, dsol, kind, pre in pp["ev"]:
        if kind == "buy" and who != pp.get("creator"):
            seen_in[who].add(pool)
            max_buy[who] = max(max_buy[who], dsol)
            if dsol >= 0.05:
                big_in[who].add(pool)


def role(w):
    if w == ME:
        return "МЫ"
    if len(big_in[w]) >= 3:
        return "парк"
    if len(seen_in[w]) >= 3:
        return "пыль-маркер" if max_buy[w] < 0.001 else "мелкий повторяющийся"
    return "посторонний"

L = [f"Пулов разобрано {len(per_pool)}; первые {MAX_S:g} с каждого; ранний вывод = до {EARLY_S:g} с. Запросов: {dict(CALLS)}"]
early = {p: pp for p, pp in per_pool.items() if pp["wd"] is not None and pp["wd"] < EARLY_S}
L.append(f"\nРАННИЙ ВЫВОД ЛИКВИДНОСТИ: {len(early)} пулов")
for p, pp in early.items():
    before = [e for e in pp["ev"] if e[3] == "buy" and pp["wd"] - 15 <= e[0] < pp["wd"]]
    big = max(before, key=lambda e: e[2], default=None)
    L.append(f"  {p[:8]} вывод на {pp['wd']} с; покупок за 15 с до вывода: {len(before)}; крупнейшая "
             + (f"{big[2]:.3f} SOL от {big[1][:8]} ({role(big[1])}) за {pp['wd'] - big[0]} с до вывода" if big else "—"))
L.append(f"\nБЕЗ РАННЕГО ВЫВОДА: {len(per_pool) - len(early)} пулов — крупнейшая покупка постороннего за первые {EARLY_S:g} с:")
for p, pp in per_pool.items():
    if p in early:
        continue
    out = [e for e in pp["ev"] if e[3] == "buy" and e[0] < EARLY_S and role(e[1]) not in ("парк", "пыль-маркер", "мелкий повторяющийся")]
    big = max(out, key=lambda e: e[2], default=None)
    L.append(f"  {p[:8]}: " + (f"{big[2]:.3f} SOL от {big[1][:8]} ({role(big[1])}) на {big[0]} с; вывод {pp['wd']}" if big else "посторонних покупок нет"))
L.append("\nКРУПНЫЕ ПОКУПКИ НЕ-БОТОВ → ВЫВОД В ТЕЧЕНИЕ 15 С:")
for lo in (0.01, 0.03, 0.05, 0.1, 0.3, 1.0):
    n = hit = 0
    for p, pp in per_pool.items():
        for e in pp["ev"]:
            if e[3] == "buy" and e[2] >= lo and role(e[1]) not in ("парк", "пыль-маркер", "мелкий повторяющийся"):
                n += 1
                hit += pp["wd"] is not None and 0 <= pp["wd"] - e[0] <= 15
    L.append(f"  покупки от {lo:g} SOL: {n}, после них вывод в течение 15 с: {hit} ({hit / n * 100:.0f}%)" if n else f"  от {lo:g} SOL: нет")
# --- the bots' buying pattern (what we want to front-run) ---
import statistics as stt
L.append("\nБОТЫ (кошельки, покупавшие в 3+ пулах): когда и на сколько покупают")
bots = sorted((w for w in big_in if len(big_in[w]) >= 3 and w != ME), key=lambda w: -len(big_in[w]))
for wlt in bots[:25]:
    bs = [(e[0], e[2], e[4]) for pp in per_pool.values() for e in pp["ev"] if e[1] == wlt and e[3] == "buy"]
    ts, amts = [b[0] for b in bs], [b[1] for b in bs]
    exact = sum(1 for b in bs if b[2] is not None and b[2] < b[1] * 1.15 + 0.01)  # its SOL before the buy ~ the buy: funded just for it
    L.append(f"  {wlt[:8]}: пулов {len(seen_in[wlt])}, покупок {len(bs)}; на {stt.median(ts):.0f} с от создания (разброс {min(ts)}–{max(ts)}); "
             f"сумма медиана {stt.median(amts):.3f} SOL (от {min(amts):.3f} до {max(amts):.3f}); баланс ≈ сумме покупки (пополнен под неё): {exact} из {len(bs)}")
L.append("\nПОСЛЕДОВАТЕЛЬНОСТЬ: первые 8 покупок каждого пула (с от создания: кошелёк, SOL)")
for p, pp in list(per_pool.items())[:40]:
    first = [e for e in pp["ev"] if e[3] == "buy"][:8]
    L.append(f"  {p[:8]} (создатель {str(pp['creator'])[:8]}, вывод {pp['wd']}): " +
             ", ".join(f"{e[0]}:{e[1][:4]}{'*' if len(big_in[e[1]]) >= 3 else ''}={e[2]:.2f}" for e in first))
with open(os.path.join(HERE, "sol_buyers.csv"), "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["pool", "creator", "t", "who", "role", "sol", "kind", "withdraw_s", "signer_sol_before"])
    for p, pp in per_pool.items():
        for e in pp["ev"]:
            w.writerow([p, pp["creator"], e[0], e[1], role(e[1]), round(e[2], 6), e[3], pp["wd"], e[4]])
print("\n".join(L))
open(os.path.join(HERE, "sol_buyers.txt"), "w", encoding="utf-8").write("\n".join(L))
