-- Gold DIMENSION 2: one row per normalized host, with hosting rollups and the
-- host's primary account (de-duplicated by most-frequent account).
with mtg as (
    select * from {{ ref('slv_meetings') }}
),

host_rollup as (
    select
        host_email,
        count(distinct meeting_id) as meetings_hosted,
        sum(duration_minutes)      as total_hosted_minutes,
        min(start_at)              as first_meeting_at,
        max(start_at)              as last_meeting_at
    from mtg
    group by host_email
),

primary_account as (
    -- de-duplication: a host may appear under several accounts; pick the one
    -- they host under most often (ties broken by account_id).
    select host_email, account_id as primary_account_id
    from mtg
    group by host_email, account_id
    qualify row_number() over (
        partition by host_email
        order by count(*) desc, account_id
    ) = 1
)

select
    h.host_email,
    pa.primary_account_id,
    h.meetings_hosted,
    h.total_hosted_minutes,
    h.first_meeting_at,
    h.last_meeting_at
from host_rollup h
left join primary_account pa on h.host_email = pa.host_email
