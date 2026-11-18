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
