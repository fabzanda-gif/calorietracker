-- SanoSync Phase 1: Exercise Library curated metadata batch 3.
-- All 53 source IDs verified in existing catalogue on 2026-11-07.
-- No automatic approval, no changes to plans/logs, and no production write
-- until this reviewed migration is deployed through the normal process.
-- Role, fatigue and complexity are qualitative coaching classifications.

with curated (
    source_id, movement_pattern, training_role, fatigue_cost,
    technical_complexity, stability_requirement
) as (
    values
        ('0489','hinge','accessory','low','medium','medium'),
        ('0983','vertical_pull','secondary','low','low','medium'),
        ('3144','horizontal_pull','secondary','low','low','medium'),
        ('0095','isolation','accessory','low','low','low'),
        ('0027','horizontal_pull','secondary','high','high','medium'),
        ('0570','vertical_pull','secondary','medium','low','medium'),
        ('2616','vertical_pull','secondary','medium','medium','medium'),
        ('0861','horizontal_pull','secondary','medium','medium','medium'),
        ('0213','horizontal_pull','secondary','medium','low','low'),
        ('0238','isolation','accessory','low','low','low'),
        ('0248','horizontal_pull','secondary','medium','medium','low'),
        ('0253','vertical_pull','primary','medium','medium','medium'),
        ('2987','vertical_pull','primary','medium','medium','medium'),
        ('0293','horizontal_pull','secondary','medium','medium','medium'),
        ('1330','horizontal_pull','secondary','medium','low','low'),
        ('0327','horizontal_pull','secondary','medium','low','low'),
        ('1328','horizontal_pull','accessory','low','medium','low'),
        ('0406','isolation','accessory','low','low','low'),
        ('0498','horizontal_pull','secondary','medium','medium','medium'),
        ('drv-kettlebell-deadlift','hinge','secondary','medium','medium','medium'),
        ('0573','hinge','accessory','low','low','low'),
        ('0581','horizontal_pull','secondary','medium','low','low'),
        ('1349','horizontal_pull','secondary','medium','low','low'),
        ('drv-lever-t-bar-row','horizontal_pull','secondary','medium','medium','low'),
        ('0207','vertical_pull','secondary','medium','low','low'),
        ('0673','vertical_pull','secondary','medium','low','low'),
        ('2327','vertical_pull','primary','medium','medium','medium'),
        ('0218','horizontal_pull','secondary','medium','low','low'),
        ('0651','vertical_pull','primary','high','medium','medium'),
        ('0752','hinge','secondary','high','medium','low'),
        ('0033','horizontal_push','secondary','high','medium','medium'),
        ('0047','horizontal_push','primary','high','medium','medium'),
        ('1269','isolation','accessory','low','medium','medium'),
        ('drv-chest-dips','horizontal_push','secondary','high','medium','high'),
        ('0301','horizontal_push','secondary','medium','medium','medium'),
        ('0302','isolation','accessory','low','medium','medium'),
        ('1274','horizontal_push','secondary','medium','medium','medium'),
        ('0319','isolation','accessory','low','medium','medium'),
        ('0321','horizontal_push','secondary','medium','medium','medium'),
        ('0340','horizontal_push','secondary','medium','medium','medium'),
        ('0620','isolation','accessory','low','medium','low'),
        ('0493','horizontal_push','accessory','low','low','low'),
        ('1299','horizontal_push','secondary','medium','low','low'),
        ('drv-lever-pec-deck-fly','isolation','accessory','low','low','low'),
        ('drv-push-ups','horizontal_push','secondary','medium','low','medium'),
        ('0175','core','accessory','low','low','low'),
        ('0226','core','accessory','low','low','low'),
        ('1764','core','secondary','medium','medium','high'),
        ('0474','core','secondary','medium','high','high'),
        ('0872','core','accessory','low','low','low'),
        ('0865','core','accessory','low','low','low'),
        ('1452','core','accessory','low','low','low'),
        ('0985','core','accessory','low','low','low')
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
  and e.active is true
  and e.approved_for_generation = false;

-- Substitutes are deliberately NOT automatically enacted. Training load,
-- equipment, movement comfort and athlete readiness must be checked.
-- Regressions are directional; substitute pairs are mirrored.
with reviewed_pairs (
    source_id, target_id, relationship, rationale
) as (
    values
        ('0198','0207','close_substitute','Cable pulldown with a different supinated grip'),
        ('0208','0218','close_substitute','Seated cable row with a wider handle and different elbow path'),
        ('0293','drv-lever-t-bar-row','substitute','Horizontal row using dumbbells or a guided T-bar lever'),
        ('0025','0047','substitute','Barbell bench press at flat or inclined bench angle; different regional emphasis'),
        ('0334','0192','close_substitute','Single arm cable variation of the lateral deltoid raise'),
        ('0308','drv-lever-pec-deck-fly','substitute','Chest fly performed with free weights or a pec-deck machine'),
        ('drv-push-ups','0493','regression','Incline push-up reduces the fraction of body weight loaded relative to floor push-up'),
        ('0253','0970','regression','Assisted pulling pattern with resistance band to reduce bodyweight demand'),
        ('0095','0406','close_substitute','Upper trapezius shrug using barbell or dumbbells'),
        ('0175','1452','substitute','Trunk flexion with cable resistance or a guided abdominal crunch machine')
),
resolved as (
    select src.id as source_exercise_id,
           dst.id as target_exercise_id,
           p.relationship,
           p.rationale
    from reviewed_pairs p
    join public.exercises src
      on src.source = 'free-exercise-db-with-videos'
     and src.source_id = p.source_id and src.active is true
    join public.exercises dst
      on dst.source = 'free-exercise-db-with-videos'
     and dst.source_id = p.target_id and dst.active is true
),
bidirectional as (
    select source_exercise_id, target_exercise_id, relationship, rationale
      from resolved
    union all
    select target_exercise_id, source_exercise_id, relationship, rationale
      from resolved
     where relationship in ('close_substitute', 'substitute')
)
insert into public.exercise_relationships
    (source_exercise_id, target_exercise_id, relationship, rationale)
select source_exercise_id, target_exercise_id, relationship, rationale
from bidirectional
on conflict (source_exercise_id,target_exercise_id,relationship)
do update set rationale = excluded.rationale;
