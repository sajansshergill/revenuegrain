{#-
  Expand each subscription across the calendar months it was active, then
  aggregate to one row per account per month with total active MRR.

  Snapshot is month-end: a subscription counts in a month if it had started
  by the last day of that month and had not yet ended by that last day.
  That avoids double-counting the upgrade month (old plan ends the day the
  new plan starts) while still attributing mid-month starts to the month.
-#}

with subscriptions as (

    select * from {{ ref('stg_subscriptions') }}

),

month_spine as (

    select month_start
    from unnest(generate_date_array(
        (select date_trunc(min(date(started_at)), month) from subscriptions),
        date_trunc(current_date(), month),
        interval 1 month
    )) as month_start

),

subscription_months as (

    select
        s.account_id,
        s.subscription_id,
        s.plan_id,
        m.month_start,
        s.mrr
    from subscriptions s
    inner join month_spine m
        on date(s.started_at) <= last_day(m.month_start, month)
       and (
            s.ended_at is null
            or date(s.ended_at) > last_day(m.month_start, month)
       )

),

account_month as (

    select
        account_id,
        month_start,
        sum(mrr)                        as mrr,
        count(distinct subscription_id) as active_subscriptions
    from subscription_months
    group by account_id, month_start

)

select * from account_month
