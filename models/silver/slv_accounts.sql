-- Silver: clean + conform accounts.
-- Exercises: conditional logic (tier CASE), string transforms (TRIM/UPPER/INITCAP),
-- data/type casts (date), and a derived age metric.
with src as (
    select * from {{ ref('brz_accounts') }}
)

select
    account_id,

    -- string normalization
    initcap(trim(account_name))                              as account_name,

    -- conditional logic: tier code -> plan name
    case tier_code::varchar
        when '1' then 'Basic'
        when '2' then 'Pro'
        when '3' then 'Business'
        when '4' then 'Enterprise'
        else 'unknown'
    end                                                      as plan_tier,

    -- string normalization (region arrives mixed-case with stray whitespace)
    upper(trim(region_code))                                 as region,

    -- data/type transformation
    signup_date::date                                        as signup_date,
    seat_count,

    -- derived metric
    datediff('day', signup_date::date, current_date)         as account_age_days

from src
