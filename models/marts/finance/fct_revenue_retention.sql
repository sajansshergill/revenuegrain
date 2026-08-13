{#-
  Month-over-month cohort retention.
  GRR caps expansion at prior MRR (can't exceed 100%); NRR includes expansion.
  Left-join so accounts that disappear (churn) contribute 0 to the numerator.
-#}

with monthly as (

    select * from {{ ref('int_subscription_monthly') }}

),

paired as (

    select
        date_add(prev.month_start, interval 1 month) as month_start,
        prev.account_id,
        prev.mrr as starting_mrr,
        coalesce(cur.mrr, 0) as current_mrr
    from monthly prev
    left join monthly cur
        on prev.account_id = cur.account_id
       and cur.month_start = date_add(prev.month_start, interval 1 month)
    where date_add(prev.month_start, interval 1 month)
        <= date_trunc(current_date(), month)

),

aggregated as (

    select
        month_start,
        sum(starting_mrr)                     as starting_mrr,
        sum(current_mrr)                      as retained_and_expanded_mrr,
        sum(least(current_mrr, starting_mrr)) as retained_capped_mrr
    from paired
    group by month_start

)

select
    month_start,
    starting_mrr,
    retained_and_expanded_mrr,
    safe_divide(retained_and_expanded_mrr, starting_mrr) as net_revenue_retention,
    safe_divide(retained_capped_mrr, starting_mrr)       as gross_revenue_retention
from aggregated
