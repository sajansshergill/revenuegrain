# Data contracts

A contract pins a model's shape so an upstream change fails loudly at build
time instead of leaking silently downstream. `stg_accounts` enforces one via
`config: {contract: {enforced: true}}`.

## stg_accounts (enforced)

| Column | Type | Constraint |
|--------|------|-----------|
| account_id | string | not null, unique |
| account_name | string | |
| segment | string | accepted: smb / mid-market / enterprise |
| industry | string | |
| country | string | |
| signup_date | date | not null |
| created_at | timestamp | |

## Source guarantees (tested, not contract-enforced)

- Every `subscription.account_id`, `usage_event.account_id`, and
  `ticket.account_id` **must** resolve to an account (`relationships` tests).
- `subscription_id`, `event_id`, `ticket_id` are unique after staging dedup.
- `mrr` and `event_count` are never negative (`positive_value`).