with movements as (

    select * from {{ ref('int_mrr_movements') }}

)

select
    {{ dbt_utils.generate_surrogate_key(['account_id', 'month_start']) }} as mrr_key,
    account_id,
    month_start,
    mrr,
    prior_mrr,
    mrr_delta,
    movement_type
from movements