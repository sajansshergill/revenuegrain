{#-
  A churned account should not carry positive MRR in any month strictly
  after its churn month. Catches lifecycle / expansion logic errors.
-#}

with health as (
    select account_id, month_start, mrr
    from {{ ref('fct_account_health') }}
),

lifecycle as (
    select account_id, churn_date
    from {{ ref('int_account_lifecycle') }}
    where churn_date is not null
)

select
    h.account_id,
    h.month_start,
    l.churn_date
from health h
inner join lifecycle l using (account_id)
where h.mrr > 0
  and h.month_start > date_trunc(l.churn_date, month)