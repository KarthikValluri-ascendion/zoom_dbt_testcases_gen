-- Silver: clean + conform meetings.
-- Exercises: conditional logic (CASE), string transforms (TRIM/UPPER/INITCAP),
-- data/type casts (timestamp, month truncation), edge cases (null duration),
-- and de-duplication (duplicate raw meeting rows).
with src as (
    select * from {{ ref('brz_meetings') }}
),

deduped as (
    select *
    from src
    -- de-duplication: the raw feed can emit the same meeting twice; keep one.
    qualify row_number() over (partition by meeting_id order by start_time) = 1
)

select
    meeting_id,
    account_id,

    -- string normalization: collapse mixed-case host identities
    trim(upper(host_email))                                  as host_email,
    initcap(trim(topic))                                     as topic,

    -- conditional logic: raw status code -> human-readable label
    case status_code
        when 'O' then 'scheduled'
        when 'S' then 'started'
        when 'E' then 'ended'
        when 'C' then 'cancelled'
        else 'unknown'
    end                                                      as meeting_status,

    -- data/type transformation
    start_time::timestamp_ntz                                as start_at,
    date_trunc('month', start_time::timestamp_ntz)::date     as meeting_month,

    -- edge case: cancelled meetings arrive with NULL duration
    coalesce(duration_minutes, 0)                            as duration_minutes,
    invited_count,

    -- derived flag
    coalesce(duration_minutes, 0) >= 60                      as is_long_meeting

from deduped
