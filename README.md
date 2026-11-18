# Solana Family 1 investigation

On-chain study of a PumpSwap pool farm on Solana («Семья 1»): pool creators, a 170-wallet pump fleet, and the money flows
treasury → sponsor → creator. Data from 16–18 Nov 2026. All times are UTC. Reports are in Russian.

No private keys, API keys or credentials are in this repository; every 87–88-character base58 string in the CSV files is a
public transaction signature.

## Contents

| Folder | What it holds |
|---|---|
| `data_40_pools/` | 40 pools of 18.11: every swap of the first 60 s (`sol_buyers.csv`), pool matrix, pool paths (`*.jsonl`), walk-forward backtest, scripts, `README.txt` with units and formulas. Files `*_v1.*` are the previous version. |
| `task_01_creator_funding/` | Task 1: funding of the creators `6e7XUsDb` and `GLEBhVYd`, links of the fleet to the family's infrastructure. |
| `task_02_dual_roles/` | Task 2: dual roles (creator / fleet / infrastructure), the `свой(создатель)` label, validation of the treasury → sponsor → creator flows, 35.02 SOL payments matched to pool creations by slot. |
| `task_03_park_wallet_flows/` | Task 3: SOL routes of the 109 fleet wallets funded by the GEKKO creator; reconciliation with task 1. |
| `task_04_fleet_cycle/` | Task 4: what the 109 wallets do in the money cycle. **Read `investigation_report_v2.md`** (corrections after review: no overlapping windows, two return series with slots, 18 funding waves, the nine 29-SOL buy-only wallets, −35.38 SOL is net SOL flow, not P&L). `investigation_report.md` is version 1, kept for comparison. |
| `task_05_ervp_pool/` | Task 5: all transactions of pool `ErVpTsjX` (fetched over RPC): the fleet traded until the withdrawal second; return series 1 equals each wallet's whole SOL balance after its last trade. |
| `task_06_nine_wallets/` | Task 6: full history (11 468 tx, RPC) of the nine 29-SOL wallets: funded by and paying back five Family 1 creators (`Czg8kh3E`, `6e7XUsDb`, `29iqxoNv`, `CPC8iEE1`, `89coAVTU`) — a signed link between them; each swap tx buys and sells back in one transaction (~43 300 SOL volume, ~703 SOL net); the "second address" is the wallet's temporary WSOL account. |
| `task_07_nine_swap_validation/` | Task 7: every swap of the nine wallets decoded from instructions (12 226 unique tx, 0 missing): all 9 677 PumpSwap tx = `sell(base_in)` (buy coin) then `buy_exact_quote_in` (sell coin) in the same pool, median 1.29% of the coin kept; all 1 970 Meteora DAMM v2 tx = buy and sell of exactly the same amount; net WSOL into pools 774.05 + 2.11 SOL; 82 transactions co-signed by a creator and 1–4 of the nine wallets burn the leftover coins and close the coin accounts with rent to the creator. |
| `task_08_residual_burns/` | Task 8: fate of the leftover coins — in 513 of 513 cases the burned amount equals bought − sold − coin fee to the raw unit; 0 token transfers; every burn is in a transaction paid by a creator and co-signed by the wallet; account rent goes to the creators. Also fixes to task 7 (1–9 co-signers, independent rent check 11 647/11 647). |
| `task_09_entry_order/` | Task 9: exact entry order (slot + index in block) of the nine into the 58 coins all nine bought: they enter 6–50 s after pool creation, never first (the coin's creator or dust bots buy first), one by one over ~75 s, first buy ~4 SOL; the order never repeats and is indistinguishable from random (Kendall W 0.0064); no round-robin. Pool creators of all 58 coins identified (49 by the wallets' own funders). |
| `task_10_sizes_timing/` | Task 10: sizes and timing from the instructions' own arguments — in every PumpSwap tx the sell amount equals the buy's minimum-out M, so the leftover is whatever the pool paid above M (0–10.3%, median 1.245%, exponential-like); Meteora buys an exact amount and sells it back (leftover 0); buy size random in [floor, ~2.1×floor], never repeated, floor 3.05 SOL or 1.52 SOL (switched for all nine at once on 18.11 02:00–12:xx); one coin at a time, a trade per wallet every ~21 s. |
| `task_10_sizes_timing/validation/` | Independent validation of task 10: `buy_arg2 == sell_arg1` in 9 677/9 677 (5 one-unit differences from the fee split rounding); exact regime switches 02:52:09 and 12:38:32 (all nine within ~2 min, no buy of the old regime afterwards); timing per wallet; sessions with 60/120/180 s gap thresholds; strictly one coin at a time at trade level. |
| `task_11_funding_and_coin_choice/` | Task 11: the nine trade the coins of whoever currently funds them (57/82 sessions vs 18.9 expected, permutation p < 0.0002); work runs in shifts (`89coAVTU` → `Czg8kh3E` → `29iqxoNv` → `CPC8iEE1` → `6e7XUsDb`); at each hand-over the nine first send their SOL to the next creator, who then funds them; creators' net funding ≈ the nine's net flow into their own pools. |
| `task_11_funding_and_coin_choice/v2/` | Task 11 v2 (review corrections): "creator" = pool creator (pool account field `creator` = init payer in 76/78; `coin_creator` empty; mint authority revoked on all 85, so the token issuer is not established); all incoming SOL from any address — only the five pool creators send more than dust; with the shift structure preserved (circular shift, block permutation) the funder ↔ coin-creator link is NOT significant (p = 0.067–0.082, only 5 funding shifts); all null distributions published. |
| `solana_summary_2026-11-18.txt` | Earlier summary: buyer patterns, families, pool matrix. |

Each task folder has its report (`investigation_report.md` or `park_flow_summary.md`), the CSV tables it is based on, and the
script that produced them (the scripts read local files of the original project; paths like `D:\bot\analysis` refer to it).

## Key addresses

| Role | Address |
|---|---|
| Treasury | `B7StC42h126Hmtkw4GoRMcaHA5ZuKawfa9fCSTV6UMSj` |
| Sponsor (also a fleet wallet) | `3azG8rmtPnNUz77a6UqBKt1ykpk3JQpLLNTaoXW31b34` |
| GEKKO creator (17.11) | `Czg8kh3EYpqgLMUdrV3X3iiBaUdgP7aZYRMYm8xU2BdL` |
| Creators 18.11 | `6e7XUsDbJyxMdDe8zEHHMgWxkC73YAe428mJRSV65sSC`, `GLEBhVYdFuP6Gh4Q7Qan66gYeSc7AjcFYC8gM7aMN6wd` |
| PumpSwap program | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` |

## Limits

The transfer export with signatures covers 2026-11-16T19:19:54Z – 2026-11-17T17:06:20Z. Swaps of 18.11 carry seconds from pool
creation, without signatures. Events taken only from our watcher logs are marked as indirect in the reports. No conclusion about a
single owner of the addresses is drawn.
