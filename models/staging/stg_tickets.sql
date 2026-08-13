with source as (

    select * from {{ source('raw', 'tickets') }}

),

renamed as (

    select
        cast(ticket_id as string)       as ticket_id,
        cast(account_id as string)      as account_id,
        cast(created_at as timestamp)   as created_at,
        cast(resolved_at as timestamp)  as resolved_at,
        lower(trim(priority))           as priority,
        lower(trim(status))             as status,
        lower(trim(category))           as category

    from source
    where ticket_id is not null

    qualify row_number() over (
        partition by ticket_id order by created_at desc
    ) = 1

)

select * from renamed