{#-
  SCD-2 history on account attributes. Captures a new row whenever an
  account's segment or lifecycle status changes.
-#}
{% snapshot accounts_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='account_id',
        strategy='check',
        check_cols=['segment', 'current_status']
    )
}}

select
    account_id,
    account_name,
    segment,
    current_status
from {{ ref('dim_accounts') }}

{% endsnapshot %}