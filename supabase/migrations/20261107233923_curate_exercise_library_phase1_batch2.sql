-- Phase 1 / Exercise Library v1: curated batch 2 (44 real source IDs)
-- Reviewed against the live SanoSync catalog on 2026-11-07.
-- Metadata-only: intentionally does NOT approve exercises for generation.
-- This PR does not deploy this migration into the production database.
-- Classification is programming guidance, not a claim of medical equivalence.
--
-- Eight symmetric substitute pairs and one additional band substitute pair.
-- No weights are promised to be equivalent when equipment changes.

with curated(
    source_id, movement_pattern, training_role, fatigue_cost,
    technical_complexity, stability_requirement
) as (
  values
    ('0054','single_leg','secondary','high','medium','high'),
    ('0116','hinge','primary','high','high','medium'),
    ('0300','hinge','secondary','medium','medium','medium'),
    ('0336','single_leg','secondary','medium','medium','high'),
    ('0432','hinge','secondary','medium','medium','medium'),
    ('drv-hip-raise-bridge','hinge','accessory','low','low','low'),
    ('new-band-triceps-pushdown','isolation','accessory','low','low','low'),
    ('2611','squat','secondary','high','low','low'),
    ('0740','squat','secondary','high','low','low'),
    ('0743','squat','primary','high','medium','low'),
    ('0597','isolation','accessory','low','low','low'),
    ('0598','isolation','accessory','low','low','low'),
    ('3006','isolation','accessory','low','low','medium'),
    ('0976','isolation','accessory','low','low','medium'),
    ('0980','isolation','accessory','low','low','medium'),
    ('0988','isolation','accessory','low','low','medium'),
    ('0991','hinge','secondary','medium','low','medium'),
    ('0582','isolation','accessory','low','low','low'),
    ('0413','squat','secondary','medium','low','medium'),
    ('0411','single_leg','secondary','high','high','high'),
    ('0417','isolation','accessory','low','low','medium'),
    ('1379','isolation','accessory','low','low','low'),
    ('0594','isolation','accessory','low','low','low'),
    ('0605','isolation','accessory','low','low','low'),
    ('0999','isolation','accessory','low','low','medium'),
    ('0409','isolation','accessory','low','medium','high'),
    ('0738','isolation','accessory','low','low','low'),
    ('0154','isolation','accessory','low','medium','medium'),
    ('0326','isolation','accessory','low','medium','medium'),
    ('0602','isolation','accessory','low','low','low'),
    ('2137','vertical_push','secondary','medium','high','medium'),
    ('0361','vertical_push','secondary','medium','medium','high'),
    ('0192','isolation','accessory','low','low','medium'),
    ('0584','isolation','accessory','low','low','low'),
    ('0310','isolation','accessory','low','low','medium'),
    ('0031','isolation','accessory','low','low','low'),
    ('0298','isolation','accessory','low','low','medium'),
    ('0322','isolation','accessory','low','medium','medium'),
    ('0351','isolation','accessory','low','medium','medium'),
    ('0194','isolation','accessory','low','low','low'),
    ('0259','horizontal_push','accessory','medium','low','medium'),
    ('0592','isolation','accessory','low','low','low'),
    ('0061','isolation','accessory','low','medium','medium'),
    ('0306','isolation','accessory','low','medium','medium')
)
update public.exercises e
set movement_pattern = c.movement_pattern,
    training_role = c.training_role,
    fatigue_cost = c.fatigue_cost,
    technical_complexity = c.technical_complexity,
    stability_requirement = c.stability_requirement,
    updated_at = now()
from curated c
where e.source = 'free-exercise-db-with-videos'
  and e.source_id = c.source_id
  and e.active = true
  and e.approved_for_generation = false;

-- Relations are directional records. Symmetric pairs are inserted in both
-- directions; equipment and athlete-readiness constraints remain mandatory
-- downstream, so these relations are not automatic swaps.
with reviewed_pairs(
    source_id, target_id, relationship, similarity_score, rationale
) as (
  values
    ('1435','0042','substitute',null,'Both are barbell squat patterns with a different torso and quadriceps demand'),
    ('1435','0743','substitute',null,'Guided hack squat is a squat-pattern alternative, with different trunk demands'),
    ('1760','0413','close_substitute',null,'Goblet and dumbbell squat are similar dumbbell squat patterns with different loading positions'),
    ('0417','0605','substitute',null,'Standing calf raise using dumbbells or a guided machine'),
    ('0585','0980','substitute',null,'Knee-extension isolation using a machine or a resistance band'),
    ('0289','0765','substitute',null,'Seated vertical shoulder press using dumbbells or a Smith machine'),
    ('0294','0031','substitute',null,'Biceps curl using dumbbells or a straight barbell'),
    ('0334','0584','substitute',null,'Lateral raise using dumbbells or a lever machine'),
    ('1723','new-band-triceps-pushdown','substitute',null,'Triceps pushdown pattern using cable or resistance band')
),
resolved as (
    select src.id as source_exercise_id,
           dst.id as target_exercise_id,
           p.relationship,
           p.similarity_score::numeric as similarity_score,
           p.rationale
    from reviewed_pairs p
    join public.exercises src
      on src.source='free-exercise-db-with-videos'
     and src.source_id=p.source_id and src.active=true
    join public.exercises dst
      on dst.source='free-exercise-db-with-videos'
     and dst.source_id=p.target_id and dst.active=true
),
bidirectional as (
    select * from resolved
    union all
    select target_exercise_id as source_exercise_id,
           source_exercise_id as target_exercise_id,
           relationship,similarity_score,rationale
    from resolved
)
insert into public.exercise_relationships
    (source_exercise_id,target_exercise_id,relationship,similarity_score,rationale)
select source_exercise_id,target_exercise_id,relationship,
       similarity_score,rationale
from bidirectional
on conflict (source_exercise_id,target_exercise_id,relationship)
do update set
    similarity_score=excluded.similarity_score,
    rationale=excluded.rationale;
