{#- One row per account with lifecycle boundaries and current status. -#}

with accounts as (

    select * from {{ ref('stg_accounts') }}

),

subscriptions as (

    select * from {{ ref('stg_subscriptions') }}

),

bounds as (

    select
        account_id,
        min(date(started_at)) as first_active_date,
        max(date(ended_at))   as last_ended_date,
        max(case when status = 'active' then 1 else 0 end) as has_active_sub
    from subscriptions
    group by account_id

)

select
    a.account_id,
    a.signup_date,
    b.first_active_date,
    -- plan changes mark the old row as churned; account-level churn is
    -- only recorded when no active subscription remains
    case
        when b.has_active_sub = 1 then null
        else b.last_ended_date
    end as churn_date,
    case
        when b.has_active_sub = 1 then 'active'
        when b.last_ended_date is not null then 'churned'
        else 'inactive'
    end as current_status
from accounts a
left join bounds b using (account_id)
