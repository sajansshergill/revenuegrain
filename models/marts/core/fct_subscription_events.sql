with subscriptions as (

    select * from {{ ref('stg_subscriptions') }}

),

plans as (

    select * from {{ ref('seed_plan_tiers') }}

)

select
    s.subscription_id,
    s.account_id,
    s.plan_id,
    p.plan_name,
    p.tier,
    s.status,
    s.mrr,
    s.billing_interval,
    s.started_at,
    s.ended_at,
    {{ get_active_months('s.started_at', 's.ended_at') }} as active_months
from subscriptions s
left join plans p on s.plan_id = p.plan_id