-- Gold DIMENSION 1: one row per account, with a lifecycle bucket.
with acc as (
    select * from {{ ref('slv_accounts') }}
)
select
    account_id,
    account_name,
    plan_tier,
    region,
    signup_date,
    seat_count,
    account_age_days,
    -- conditional logic: lifecycle stage from account age
    case
        when account_age_days < 90  then 'new'
        when account_age_days < 365 then 'growing'
        else 'mature'
    end as lifecycle_stage
from acc
