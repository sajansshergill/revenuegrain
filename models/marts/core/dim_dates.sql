with spine as (

    select date_day
    from unnest(
        generate_date_array(
            '{{ var("start_date") }}',
            current_date(),
            interval 1 day
        )
    ) as date_day

)

select
    date_day,
    extract(year    from date_day) as year,
    extract(quarter from date_day) as quarter,
    extract(month   from date_day) as month,
    extract(day     from date_day) as day,
    date_trunc(date_day, month)    as month_start,
    format_date('%Y-%m', date_day) as year_month,
    format_date('%A', date_day)    as day_name,
    extract(dayofweek from date_day) between 2 and 6 as is_weekday
from spine
