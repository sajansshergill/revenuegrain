{#- Fails on any value < 0 (nulls pass). Usage: tests: [positive_value] -#}
{% test positive_value(model, column_name) %}

select {{ column_name }}
from {{ model }}
where {{ column_name }} < 0

{% endtest %}