with accounts as (

    select * from {{ ref('stg_accounts') }}

),

lifecycle as (

    select * from {{ ref('int_account_lifecycle') }}

)

select
    a.account_id,
    a.account_name,
    a.segment,
    a.industry,
    a.country,
    a.signup_date,
    l.first_active_date,
    l.churn_date,
    l.current_status
from accounts a
left join lifecycle l using (account_id)