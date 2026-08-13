# Data quality & testing

Data quality is treated as an engineering concern here, carried over from a
QA/SDET background: the pipeline refuses to ship a number it can't defend, and
CI blocks a merge on any failing test.

## Test inventory

### Built-in schema tests
- `not_null` / `unique` on every primary key (staging PKs, mart surrogate keys).
- `relationships` from subscriptions, usage events, and tickets back to accounts.
- `accepted_values` on `segment`, `status`, `priority`, `billing_interval`,
  `movement_type`, `current_status`.

### Custom generic tests (`tests/generic/`)
- `positive_value` — MRR, event_count, and derived amounts are never negative.
- `rate_between_zero_and_one` — GRR stays within [0, 1].

### Range tests (`dbt-expectations`)
- `net_revenue_retention` within [0, 3] (allows expansion above 100%).
- `health_score` within [0, 100].

### Singular tests (`tests/singular/`)
- `assert_segment_mrr_reconciles_to_total` — MRR in the fact equals the sum of
  per-account MRR in the intermediate layer. Catches double-counting joins.
- `assert_no_active_and_churned_same_month` — a churned account carries no
  positive MRR after its churn month. Catches lifecycle/expansion errors.

### Source freshness
- Warn at 36h / error at 72h on `accounts`, `subscriptions`, `usage_events`.

## Contracts
`stg_accounts` enforces a data contract (see `data_contracts.md`).

## What is deliberately NOT covered (honest gaps)

- **No anomaly detection on metric *values*** — tests assert structural validity
  (ranges, keys, reconciliation), not that a 40% MRR drop is "wrong". A sudden
  legitimate-looking drift would pass. A monitoring layer (e.g. Elementary) would
  close this.
- **No cross-system reconciliation** — there is no billing system to reconcile
  MRR against; the synthetic generator is treated as ground truth.
- **Freshness is nominal** — the data is generated in a batch, so freshness
  thresholds are illustrative of the pattern rather than load-bearing.
- **The text-to-metric layer is not validated end-to-end** — generated SQL is
  constrained to the semantic layer but is not automatically executed and
  checked against expected results.

Stating these is the point: a quality layer you can't describe the limits of
isn't a quality layer.