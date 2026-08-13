{#- Daily usage per account: event volume and feature breadth. -#}

with events as (

    select * from {{ ref('stg_usage_events') }}

)

select
    account_id,
    event_date,
    date_trunc(event_date, month)   as month_start,
    count(distinct feature_key)     as distinct_features_used,
    sum(event_count)                as total_events
from events
group by account_id, event_date, month_start