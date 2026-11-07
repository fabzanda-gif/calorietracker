-- Exercise Library v1: batch 4, thirty catalog-verified exercises.
-- The four versioned batches plus the ten golden exercises now cover 154
-- distinct catalog records with intentional curation metadata.
-- These records remain unapproved for program generation.
-- No existing workout plan, logged set or exercise approval is modified.

with curated (
    source_id, movement_pattern, training_role, fatigue_cost,
    technical_complexity, stability_requirement
) as (
    values
        ('drv-chin-ups-pull-ups','vertical_pull','primary','high','medium','medium'),
        ('drv-ring-high-row','horizontal_pull','secondary','medium','medium','high'),
        ('0499','horizontal_pull','secondary','medium','medium','medium'),
        ('0604','isolation','accessory','low','low','low'),
        ('0329','isolation','accessory','low','low','low'),
        ('1329','horizontal_pull','secondary','medium','medium','medium'),
        ('3012','isolation','accessory','low','medium','medium'),
        ('drv-commando-pull-up','vertical_pull','secondary','high','high','high'),
        ('drv-cable-bar-lateral-pulldown-wide-shoulder-grip','vertical_pull','secondary','medium','low','low'),
        ('drv-band-high-fly','isolation','accessory','low','medium','medium'),
        ('drv-rotate-push-up-female','horizontal_push','secondary','medium','medium','high'),
        ('1277','isolation','accessory','low','medium','high'),
        ('1278','isolation','accessory','low','medium','high'),
        ('0297','isolation','accessory','low','low','low'),
        ('0333','isolation','accessory','low','medium','medium'),
        ('2188','isolation','accessory','low','medium','medium'),
        ('0190','isolation','accessory','low','low','low'),
        ('0229','isolation','accessory','low','low','low'),
        ('0374','isolation','accessory','low','medium','low'),
        ('1451','horizontal_push','secondary','medium','low','low'),
        ('1005','core','accessory','low','low','medium'),
        ('0230','core','accessory','low','medium','medium'),
        ('0862','core','accessory','low','medium','medium'),
        ('1338','core','accessory','low','low','medium'),
        ('0325','core','secondary','medium','medium','medium'),
        ('0981','core','accessory','medium','medium','medium'),
        ('0600','core','accessory','low','medium','low'),
        ('0826','core','secondary','medium','medium','high'),
        ('drv-v-up','core','secondary','medium','medium','medium'),
        ('drv-sit-ups','core','accessory','low','low','low')
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

-- Relations are suggestions for review, not automatic substitutions;
-- progressive overload and exercise choice still require user confirmation.
with reviewed_pairs (
    source_id, target_id, relationship, rationale
) as (
    values
        ('drv-chin-ups-pull-ups','0970','regression','Band-assisted pull-up reduces bodyweight demand'),
        ('0406','0604','substitute','Dumbbell shrug and lever shrug share upper-trapezius elevation pattern'),
        ('0297','0592','substitute','Concentration curl and preacher curl share elbow flexion isolation intent'),
        ('drv-push-ups','drv-rotate-push-up-female','progression','Rotational push-up adds rotational stability demand'),
        ('0175','1005','substitute','Trunk-flexion work using cable or a resistance band'),
        ('drv-cable-bar-lateral-pulldown-wide-shoulder-grip','0198','close_substitute','Wide-grip cable pulldown compared with standard cable pulldown')
),
resolved as (
    select src.id as source_exercise_id,
           dst.id as target_exercise_id,
           p.relationship,
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
    select source_exercise_id, target_exercise_id, relationship, rationale
    from resolved
    union all
    select target_exercise_id, source_exercise_id, relationship, rationale
    from resolved
    where relationship in ('close_substitute','substitute')
)
insert into public.exercise_relationships
    (source_exercise_id,target_exercise_id,relationship,rationale)
select source_exercise_id,target_exercise_id,relationship,rationale
from bidirectional
on conflict (source_exercise_id,target_exercise_id,relationship)
do update set rationale=excluded.rationale;
