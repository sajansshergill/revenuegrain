with usage as (

    select * from {{ ref('stg_usage_events') }}

),

catalog as (

    select * from {{ ref('seed_feature_catalog') }}

)

select
    u.account_id,
    u.feature_key,
    c.feature_name,
    c.category,
    sum(u.event_count)   as event_count,
    min(u.event_date)    as first_used_date,
    max(u.event_date)    as last_used_date
from usage u
left join catalog c on u.feature_key = c.feature_key
group by u.account_id, u.feature_key, c.feature_name, c.category