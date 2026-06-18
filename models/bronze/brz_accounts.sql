-- Bronze: 1:1 pass-through of the raw accounts seed. No business logic.
with src as (
    select * from {{ ref('raw_accounts') }}
)
select
    account_id,
    account_name,
    tier_code,
    region_code,
    signup_date,
    seat_count
from src
