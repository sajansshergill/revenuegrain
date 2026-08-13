{#- Number of whole calendar months a subscription is active (inclusive). -#}
{% macro get_active_months(started_at, ended_at) %}
    date_diff(
        date_trunc(coalesce(date({{ ended_at }}), current_date()), month),
        date_trunc(date({{ started_at }}), month),
        month
    ) + 1
{% endmacro %}