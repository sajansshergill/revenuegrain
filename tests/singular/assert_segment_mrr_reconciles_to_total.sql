{#-
  Total MRR per month in the fact must equal (1) the sum of per-account MRR
  in the intermediate layer and (2) the sum of MRR after joining to segment
  on dim_accounts. Catches double-counting joins and orphaned fact rows.
-#}

with account_level as (
    select month_start, sum(mrr) as source_mrr
    from {{ ref('int_subscription_monthly') }}
    group by month_start
),

fact_level as (
    select month_start, sum(mrr) as fact_mrr
    from {{ ref('fct_mrr_monthly') }}
    group by month_start
),

segment_level as (
    select
        f.month_start,
        sum(f.mrr) as segment_mrr
    from {{ ref('fct_mrr_monthly') }} f
    inner join {{ ref('dim_accounts') }} a using (account_id)
    group by f.month_start
)

select
    coalesce(f.month_start, a.month_start) as month_start,
    a.source_mrr,
    f.fact_mrr,
    s.segment_mrr,
    abs(coalesce(a.source_mrr, 0) - coalesce(f.fact_mrr, 0)) as vs_intermediate,
    abs(coalesce(s.segment_mrr, 0) - coalesce(f.fact_mrr, 0)) as vs_segment
from fact_level f
full outer join account_level a using (month_start)
left join segment_level s using (month_start)
where abs(coalesce(a.source_mrr, 0) - coalesce(f.fact_mrr, 0)) > 0.01
   or abs(coalesce(s.segment_mrr, 0) - coalesce(f.fact_mrr, 0)) > 0.01
