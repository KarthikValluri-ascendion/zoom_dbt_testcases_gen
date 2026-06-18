-- Silver: clean + conform participant join events.
-- Exercises: de-duplication (multiple join events per attendee),
-- string transforms (TRIM/UPPER), data/type casts (timestamps),
-- and edge cases (clock skew where leave precedes join).
with src as (
    select * from {{ ref('brz_participants') }}
),

deduped as (
    select *
    from src
    -- de-duplication: an attendee can emit several join events for one meeting;
    -- keep only the earliest join.
    qualify row_number() over (
        partition by meeting_id, participant_id
        order by join_time::timestamp_ntz
    ) = 1
)

select
    meeting_id,
    participant_id,

    -- string normalization
    trim(upper(participant_email))                           as participant_email,

    -- data/type transformation
    join_time::timestamp_ntz                                 as join_at,
    leave_time::timestamp_ntz                                as leave_at,

    -- edge case: clock skew can make leave precede join -> clamp negatives to 0
    case
        when datediff('minute', join_time::timestamp_ntz, leave_time::timestamp_ntz) < 0
            then 0
        else datediff('minute', join_time::timestamp_ntz, leave_time::timestamp_ntz)
    end                                                      as attended_minutes

from deduped
