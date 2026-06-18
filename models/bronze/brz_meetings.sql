-- Bronze: 1:1 pass-through of the raw meetings seed. No business logic.
-- (Exempt from the coverage gate via ttd_exempt_prefixes = ['brz_'].)
with src as (
    select * from {{ ref('raw_meetings') }}
)
select
    meeting_id,
    account_id,
    host_email,
    topic,
    status_code,
    start_time,
    duration_minutes,
    invited_count
from src
