with source as (

    select * from {{ source('raw', 'accounts') }}

),

renamed as (

    select
        cast(account_id as string)     as account_id,
        trim(account_name)             as account_name,
        lower(trim(segment))           as segment,
        lower(trim(industry))          as industry,
        upper(trim(country))           as country,
        date(signup_date)              as signup_date,
        cast(created_at as timestamp)  as created_at

    from source
    where account_id is not null

    -- collapse the seeded duplicate rows, keeping the latest record
    qualify row_number() over (
        partition by account_id order by created_at desc
    ) = 1

)

select * from renamed