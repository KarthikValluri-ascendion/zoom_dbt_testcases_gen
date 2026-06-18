--============================================================================
-- snowflake_explore.sql  -  "SEE THE PROBLEM" worksheet for the Zoom TTD demo
--============================================================================
-- Run these AFTER you have populated the warehouse once:
--     dbt seed && dbt build --vars 'ttd_enforce: false'
-- (the --vars bypass lets the build run even though fct_meetings has no tests,
--  so we have real rows to look at before we turn the gate on.)
--
-- Schemas (from generate_schema_name.sql, local/main run -> ZOOM_* in DB01):
--     seeds + bronze views -> DB01.ZOOM_BRONZE
--     silver views         -> DB01.ZOOM_SILVER
--     gold tables          -> DB01.ZOOM_GOLD
--
-- The whole point: the RAW data is messy, the SILVER layer cleans it, and the
-- GOLD fact (fct_meetings) computes an engagement_score with NO test guarding
-- its edge cases. Use this worksheet to show the client *why* the gate matters.
--============================================================================

use database DB01;
use warehouse COMPUTE_WH;

------------------------------------------------------------------------------
-- 1) THE RAW MESS  (DB01.ZOOM_BRONZE.RAW_MEETINGS)
--    point out: mixed-case host emails (Alice@ACME.com vs alice@acme.com),
--    cryptic status codes (O/S/E/C), a NULL duration (M0005, cancelled),
--    and a duplicated meeting row (M0008 appears twice).
------------------------------------------------------------------------------
select *
from DB01.ZOOM_BRONZE.RAW_MEETINGS
order by meeting_id;

-- 1a) Prove the duplicate exists - this is what the silver QUALIFY de-dupes.
--     point out: M0008 has COUNT = 2 in raw.
select meeting_id, count(*) as raw_rows
from DB01.ZOOM_BRONZE.RAW_MEETINGS
group by meeting_id
having count(*) > 1
order by meeting_id;

-- 1b) Duplicate participant join events (same attendee, same meeting, twice).
--     point out: these collapse to one "earliest join" in silver.
select meeting_id, participant_id, count(*) as raw_join_events
from DB01.ZOOM_BRONZE.RAW_PARTICIPANTS
group by meeting_id, participant_id
having count(*) > 1
order by meeting_id, participant_id;

------------------------------------------------------------------------------
-- 2) THE SILVER CLEAN-UP  (DB01.ZOOM_SILVER.*)
--    point out: status codes are now words, emails are UPPER+TRIM'd,
--    the duplicate M0008 is gone, and the NULL duration became 0.
------------------------------------------------------------------------------
select
    meeting_id,
    host_email,            -- normalized (TRIM/UPPER)
    meeting_status,        -- CASE: O/S/E/C -> scheduled/started/ended/cancelled
    duration_minutes,      -- COALESCE(null, 0): M0005 is now 0
    is_long_meeting        -- derived flag (>= 60 min)
from DB01.ZOOM_SILVER.SLV_MEETINGS
order by meeting_id;

-- 2a) Clock-skew edge case: leave before join -> attended_minutes clamped to 0.
--     point out: any row where leave_at < join_at still shows 0, never negative.
select
    meeting_id,
    participant_id,
    join_at,
    leave_at,
    attended_minutes       -- CASE clamp: negatives forced to 0
from DB01.ZOOM_SILVER.SLV_PARTICIPANTS
order by meeting_id, participant_id;

------------------------------------------------------------------------------
-- 3) THE UNTESTED FACT  (DB01.ZOOM_GOLD.FCT_MEETINGS)  <-- the RED fixture
--    engagement_score = least(100, round(avg_attended / nullif(duration,0) * 100))
--    Three edge cases live here and NOTHING tests them:
--      * cancelled meeting (M0005, duration 0) -> nullif divide guard -> NULL
--      * meeting with no participants           -> coalesce -> 0
--      * very engaged short meeting             -> least(...) caps at 100
--    point out: a one-line change to this formula could silently break every
--    one of these, and no test would catch it. THAT is what the gate prevents.
------------------------------------------------------------------------------
select
    meeting_id,
    meeting_status,
    duration_minutes,
    participant_count,
    avg_attended_minutes,
    engagement_score
from DB01.ZOOM_GOLD.FCT_MEETINGS
order by engagement_score nulls last, meeting_id;

-- 3a) Isolate just the edge-case rows for the narration.
--     point out: NULL score (cancelled), 0 score (no participants), 100 cap.
select
    meeting_id,
    meeting_status,
    duration_minutes,
    participant_count,
    engagement_score,
    case
        when engagement_score is null then 'divide-by-zero guard (nullif) -> NULL'
        when participant_count = 0    then 'no participants (coalesce) -> 0'
        when engagement_score = 100   then 'capped by least(100, ...)'
        else 'normal'
    end as edge_case_explanation
from DB01.ZOOM_GOLD.FCT_MEETINGS
where engagement_score is null
   or participant_count = 0
   or engagement_score = 100
order by engagement_score nulls last, meeting_id;
