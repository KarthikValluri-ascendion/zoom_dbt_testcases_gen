-- Gold FACT: one row per meeting with attendance rollups and an engagement
-- score. THIS MODEL DELIBERATELY SHIPS WITH NO TESTS -- it is the RED state the
-- coverage gate is meant to catch on a pull request.
--
-- Notable logic the unit tests should pin:
--   * left join to participants -> coalesce 0 (cancelled/scheduled meetings)
--   * engagement_score guarded against divide-by-zero with nullif(...)
--   * engagement_score capped at 100 with least(...)
with mtg as (
    select * from {{ ref('slv_meetings') }}
),

part as (
    select
        meeting_id,
        count(*)              as participant_count,
        sum(attended_minutes) as total_attended_minutes,
        avg(attended_minutes) as avg_attended_minutes
    from {{ ref('slv_participants') }}
    group by meeting_id
)

select
    m.meeting_id,
    m.account_id,
    m.host_email,
    m.meeting_status,
    m.start_at,
    m.meeting_month,
    m.duration_minutes,
    m.invited_count,

    -- edge case: meetings with no participants -> 0 (not null)
    coalesce(p.participant_count, 0)        as participant_count,
    coalesce(p.total_attended_minutes, 0)   as total_attended_minutes,
    coalesce(p.avg_attended_minutes, 0)     as avg_attended_minutes,

    -- conditional + divide-by-zero guard, capped at 95
    least(
        95,
        round(coalesce(p.avg_attended_minutes, 0) / nullif(m.duration_minutes, 0) * 100, 1)
    )                                       as engagement_score

from mtg m
left join part p on m.meeting_id = p.meeting_id
