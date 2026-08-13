{#- Fails on any non-null value outside [0, 1]. For rates/ratios. -#}
{% test rate_between_zero_and_one(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} is not null
  and ({{ column_name }} < 0 or {{ column_name }} > 1)

{% endtest %}