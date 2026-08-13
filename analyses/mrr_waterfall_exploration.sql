-- Ad-hoc exploration (compiled by dbt but never materialized).
-- MRR waterfall: how much each movement type contributed per month.

select
    month_start,
    movement_type,
    count(*)           as account_count,
    sum(prior_mrr)     as beginning_mrr,
    sum(mrr)           as ending_mrr,
    sum(mrr_delta)     as net_mrr_change
from {{ ref('int_mrr_movements') }}
group by month_start, movement_type
order by month_start, movement_type
