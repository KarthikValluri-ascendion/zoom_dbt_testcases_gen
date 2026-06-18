-- Singular test: every account must resolve to a known plan tier. An 'unknown'
-- means a tier code slipped through the CASE mapping unhandled. Returns
-- offending rows (=> fails) when that happens.
select
    account_id,
    plan_tier
from {{ ref('slv_accounts') }}
where plan_tier = 'unknown'
