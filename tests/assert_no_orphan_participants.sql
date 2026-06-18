-- Singular test: referential integrity -- every participant event must belong
-- to a known meeting. Returns offending rows (=> fails) for any orphan.
-- (Targets the silver layer; deliberately does NOT reference fct_meetings, so
--  fct_meetings stays the untested RED fixture for the coverage-gate demo.)
select p.meeting_id
from {{ ref('slv_participants') }} p
left join {{ ref('slv_meetings') }} m
       on p.meeting_id = m.meeting_id
where m.meeting_id is null
