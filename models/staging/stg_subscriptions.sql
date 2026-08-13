with source as (

    select * from {{ source('raw', 'subscriptions') }}

),

renamed as (

    select
        cast(subscription_id as string)     as subscription_id,
        cast(account_id as string)          as account_id,
        cast(plan_id as string)             as plan_id,
        lower(trim(status))                 as status,
        {{ cents_to_dollars('mrr_cents') }} as mrr,
        cast(started_at as timestamp)       as started_at,
        cast(ended_at as timestamp)         as ended_at,
        lower(trim(billing_interval))       as billing_interval

    from source
    where subscription_id is not null

    qualify row_number() over (
        partition by subscription_id order by started_at desc
    ) = 1

)

select * from renamed
