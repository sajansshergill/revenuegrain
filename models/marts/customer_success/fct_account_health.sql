{#-
  Composite account health score (0-100), grain account x month:
    usage_score   (0-50)  scaled event volume
    support_score (0-30)  penalised by high-priority tickets
    revenue_score (0-20)  paying accounts score full
-#}

with mrr as (

    select account_id, month_start, mrr
    from {{ ref('int_subscription_monthly') }}

),

usage as (

    select
        account_id,
        month_start,
        sum(total_events)          as monthly_events,
        avg(distinct_features_used) as avg_features_used
    from {{ ref('int_usage_daily_rollup') }}
    group by account_id, month_start

),

tickets as (

    select
        account_id,
        date_trunc(date(created_at), month)              as month_start,
        count(*)                                         as ticket_count,
        countif(priority in ('high', 'urgent'))          as high_priority_tickets
    from {{ ref('stg_tickets') }}
    group by account_id, month_start

),

combined as (

    select
        m.account_id,
        m.month_start,
        m.mrr,
        coalesce(u.monthly_events, 0)        as monthly_events,
        coalesce(u.avg_features_used, 0)     as avg_features_used,
        coalesce(t.ticket_count, 0)          as ticket_count,
        coalesce(t.high_priority_tickets, 0) as high_priority_tickets
    from mrr m
    left join usage u   using (account_id, month_start)
    left join tickets t using (account_id, month_start)

),

scored as (

    select
        *,
        least(50.0, monthly_events / 10.0)               as usage_score,
        greatest(0.0, 30.0 - high_priority_tickets * 10)  as support_score,
        case when mrr > 0 then 20.0 else 0.0 end          as revenue_score
    from combined

)

select
    {{ dbt_utils.generate_surrogate_key(['account_id', 'month_start']) }} as health_key,
    account_id,
    month_start,
    mrr,
    monthly_events,
    avg_features_used,
    ticket_count,
    high_priority_tickets,
    round(usage_score + support_score + revenue_score, 1) as health_score
from scored