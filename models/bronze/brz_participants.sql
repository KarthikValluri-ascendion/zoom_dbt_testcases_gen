-- Bronze: 1:1 pass-through of the raw participants seed. No business logic.
with src as (
    select * from {{ ref('raw_participants') }}
)
select
    meeting_id,
    participant_id,
    participant_email,
    join_time,
    leave_time
from src
