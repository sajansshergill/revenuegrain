# Architecture

## Data flow
Python generator ──▶ BigQuery raw ──▶ staging ──▶ intermediate ──▶ marts ──▶ BI + text-to-metric
(views) (views) (tables)

## Layers

**Staging** (`stg_*`, views) — one model per source table. Type-casts, renames,
lowercases, and deduplicates. This is the only layer that reads from `source()`.
Data contracts are enforced on `stg_accounts`.

**Intermediate** (`int_*`, views) — reusable business logic that more than one
mart needs, and any fan-out resolution (e.g. expanding subscriptions across the
months they were active). Never exposed to BI.

**Marts** (`fct_*` / `dim_*`, tables) — business-ready, at a documented grain,
grouped by consuming domain (`core`, `finance`, `customer_success`).

## Grain decisions

| Model | Grain |
|-------|-------|
| `fct_mrr_monthly` | one row per account per month |
| `fct_revenue_retention` | one row per month |
| `fct_account_health` | one row per account per month |
| `fct_subscription_events` | one row per subscription |
| `dim_accounts` | one row per account |

Getting the grain explicit and testing the primary key at that grain is the
single most important correctness guarantee in the project.

## MRR snapshot rule

`int_subscription_monthly` uses a **month-end** snapshot: a subscription counts
in a month if it had started by the last day of that month and had not ended by
that last day. Plan upgrades (old `ended_at` = new `started_at`) therefore
handoff cleanly with no double-counted month. `int_mrr_movements` adds a single
`mrr = 0` row in the month after an account's last paid month so `churn` is a
real movement type rather than a missing row.