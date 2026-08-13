{#-
  Classify each account-month against the prior month:
  new / expansion / contraction / churn / retained, with the MRR delta.

  int_subscription_monthly only contains months with positive MRR, so a
  synthetic mrr=0 row is added for the month after an account's last
  active month. That is the only way `churn` can appear.
-#}

with monthly as (

    select
        account_id,
        month_start,
        mrr
    from {{ ref('int_subscription_monthly') }}

),

churn_months as (

    select
        account_id,
        date_add(max(month_start), interval 1 month) as month_start,
        0.0 as mrr
    from monthly
    group by account_id
    having date_add(max(month_start), interval 1 month)
         <= date_trunc(current_date(), month)

),

spine as (

    select account_id, month_start, mrr from monthly

    union all

    select
        c.account_id,
        c.month_start,
        c.mrr
    from churn_months c
    left join monthly m
        on c.account_id = m.account_id
       and c.month_start = m.month_start
    where m.account_id is null

),

with_prior as (

    select
        account_id,
        month_start,
        mrr,
        coalesce(
            lag(mrr) over (partition by account_id order by month_start),
            0
        ) as prior_mrr
    from spine

),

classified as (

    select
        account_id,
        month_start,
        mrr,
        prior_mrr,
        mrr - prior_mrr as mrr_delta,
        case
            when prior_mrr = 0 and mrr > 0 then 'new'
            when prior_mrr > 0 and mrr = 0 then 'churn'
            when mrr > prior_mrr           then 'expansion'
            when mrr < prior_mrr           then 'contraction'
            else 'retained'
        end as movement_type
    from with_prior

)

select * from classified
