-- Exercise Library Phase 1: first reviewed, conservative metadata batch.
-- All source IDs below were checked against the live catalogue on 2026-11-07.
-- Does NOT change approved_for_generation, exercise names, workout plans or logs.
-- The generator continues to use only its already-approved golden exercises.
--
-- Run via normal Supabase migration deployment AFTER PR review.
-- This migration is idempotent for the metadata values and relationships.

with curated(
  source_id, movement_pattern, training_role, fatigue_cost,
  technical_complexity, stability_requirement
) as (
  values
    ('0042','squat','primary','high','high','medium'),
    ('1760','squat','secondary','medium','low','medium'),
    ('0577','horizontal_push','secondary','medium','low','low'),
    ('0308','isolation','accessory','low','medium','medium'),
    ('0974','vertical_pull','secondary','medium','low','low'),
    ('0990','horizontal_pull','secondary','low','low','medium'),
    ('0970','vertical_pull','secondary','medium','medium','medium'),
    ('1429','vertical_pull','primary','high','medium','medium'),
    ('0178','isolation','accessory','low','low','medium'),
    ('0200','isolation','accessory','low','low','low'),
    ('0294','isolation','accessory','low','low','medium'),
    ('2407','isolation','accessory','low','low','low'),
    ('0585','isolation','accessory','low','low','low'),
    ('0586','isolation','accessory','low','low','low'),
    ('0599','isolation','accessory','low','low','low'),
    ('0705','core','accessory','low','medium','medium'),
    ('0274','core','accessory','low','low','low'),
    ('0765','vertical_push','secondary','medium','medium','low')
)
update public.exercises e
set movement_pattern=c.movement_pattern,
    training_role=c.training_role,
    fatigue_cost=c.fatigue_cost,
    technical_complexity=c.technical_complexity,
    stability_requirement=c.stability_requirement,
    updated_at=now()
from curated c
where e.source='free-exercise-db-with-videos'
  and e.source_id=c.source_id
  and e.active=true
  and e.approved_for_generation=false;

-- Directional relations: substitute means similar training intent, not
-- identical load. Consumers MUST still check equipment and readiness.
-- Only pairings with an unambiguous shared movement are included.
with pairs(source_id,target_id,relationship,score,rationale) as (
  values
    ('0198','0974','close_substitute',0.92,'Vertical cable pulldown: narrow-grip variation'),
    ('0208','0990','substitute',0.76,'Horizontal seated row with resistance band instead of cable'),
    ('0334','0178','close_substitute',0.90,'Lateral deltoid raise with cable instead of dumbbell'),
    ('1723','0200','close_substitute',0.92,'Cable triceps pushdown using rope attachment'),
    ('0294','2407','close_substitute',0.89,'Elbow flexion with EZ bar instead of dumbbells'),
    ('0586','0599','close_substitute',0.90,'Knee flexion on seated instead of lying leg-curl machine'),
    ('0025','0577','substitute',0.78,'Horizontal press with a guided chest press machine'),
    ('1435','1760','regression',0.73,'Goblet squat with dumbbell to practise squat pattern with lower technical demands')
),
resolved as (
  select src.id as source_exercise_id,
         dst.id as target_exercise_id,
         p.relationship,
         p.score,
         p.rationale
  from pairs p
  join public.exercises src
    on src.source='free-exercise-db-with-videos'
   and src.source_id=p.source_id and src.active=true
  join public.exercises dst
    on dst.source='free-exercise-db-with-videos'
   and dst.source_id=p.target_id and dst.active=true
),
symmetric as (
  select source_exercise_id,target_exercise_id,relationship,score,rationale
  from resolved
  union all
  select target_exercise_id,source_exercise_id,relationship,score,rationale
  from resolved
  where relationship in ('close_substitute','substitute')
)
insert into public.exercise_relationships
  (source_exercise_id,target_exercise_id,relationship,similarity_score,rationale)
select source_exercise_id,target_exercise_id,relationship,score,rationale
from symmetric
on conflict (source_exercise_id,target_exercise_id,relationship)
do update set similarity_score=excluded.similarity_score,
              rationale=excluded.rationale;
