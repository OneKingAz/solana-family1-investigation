"""18.11 (analyst): one wallet-role definition for all Solana scripts, applied to the existing sol_buyers.csv without new requests.
«парк» = bought >= 0.05 SOL in 3+ pools; «пыль-маркер» = bought in 3+ pools and never more than 0.001 SOL; «мелкий повторяющийся» =
3+ pools, the rest; «посторонний» = fewer than 3 pools; «МЫ» = our wallet. The creator's own buys do not count. The old file is kept
as sol_buyers_v1.csv. Usage: python sol_roles.py"""
import collections, csv, os

HERE = os.path.dirname(os.path.abspath(__file__))
ME = "CqMsFPRFuSqCuxuK79kpw7cFm5ud8MoWBnqT27VfDx6J"
SRC = os.path.join(HERE, "sol_buyers.csv")
rows = list(csv.DictReader(open(SRC, encoding="utf-8-sig"), delimiter=";"))
seen, big, mx = collections.defaultdict(set), collections.defaultdict(set), collections.defaultdict(float)
for r in rows:
    if r["kind"] == "buy" and r["who"] != r["creator"]:
        s = float(r["sol"])
        seen[r["who"]].add(r["pool"])
        mx[r["who"]] = max(mx[r["who"]], s)
        if s >= 0.05:
            big[r["who"]].add(r["pool"])


def role(w, creator):
    if w == ME:
        return "МЫ"
    if w == creator:
        return "создатель"
    if len(big[w]) >= 3:
        return "парк"
    if len(seen[w]) >= 3:
        return "пыль-маркер" if mx[w] < 0.001 else "мелкий повторяющийся"
    return "посторонний"


for r in rows:
    r["role"] = role(r["who"], r["creator"])
with open(SRC, "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()), delimiter=";")
    w.writeheader()
    w.writerows(rows)
cnt = collections.Counter()
for wlt in seen:
    cnt[role(wlt, "")] += 1
print("кошельков по ролям:", dict(cnt))
print("повторяющихся (3+ пулов):", sum(1 for wlt in seen if len(seen[wlt]) >= 3), "; парк:", sum(1 for wlt in big if len(big[wlt]) >= 3))
