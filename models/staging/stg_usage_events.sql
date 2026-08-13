with source as (

    select * from {{ source('raw', 'usage_events') }}

),

renamed as (

    select
        cast(event_id as string)        as event_id,
        cast(account_id as string)      as account_id,
        lower(trim(feature_key))        as feature_key,
        cast(event_ts as timestamp)     as event_ts,
        date(event_ts)                  as event_date,
        -- default a missing count to 1 event
        coalesce(cast(event_count as int64), 1) as event_count

    from source
    where event_id is not null
      and account_id is not null

    qualify row_number() over (
        partition by event_id order by event_ts
    ) = 1

)

select * from renamed