alter table public.exercises
    add column if not exists legacy_key text null;

create unique index if not exists exercises_legacy_key_unique
    on public.exercises(legacy_key)
    where legacy_key is not null;

with curated(
    source_id,
    legacy_key,
    movement_pattern,
    training_role,
    fatigue_cost,
    technical_complexity,
    stability_requirement,
    tracking_type,
    load_convention,
    strength_score,
    hypertrophy_score,
    general_fitness_score
) as (
    values
        ('1435','back_squat','squat','primary','high','high','medium','reps_load','total',5,4,4),
        ('0025','bench_press','horizontal_push','primary','high','medium','medium','reps_load','total',5,5,4),
        ('0334','lateral_raise','isolation','accessory','low','low','medium','reps_load','per_hand',1,5,4),
        ('0464','plank','core','accessory','low','low','low','duration','bodyweight',1,3,5),
        ('0553','overhead_press','vertical_push','primary','high','high','medium','reps_load','total',5,4,4),
        ('0198','lat_pulldown','vertical_pull','secondary','medium','low','low','reps_load','reported',3,5,5),
        ('0314','incline_dumbbell_press','horizontal_push','secondary','medium','medium','high','reps_load','per_hand',3,5,4),
        ('0208','cable_row','horizontal_pull','secondary','medium','low','low','reps_load','reported',3,5,5),
        ('1723','triceps_pushdown','isolation','accessory','low','low','low','reps_load','reported',1,5,4),
        ('0289','dumbbell_shoulder_press','vertical_push','secondary','medium','medium','high','reps_load','per_hand',3,5,4)
)
update public.exercises e
set
    legacy_key = c.legacy_key,
    movement_pattern = c.movement_pattern,
    training_role = c.training_role,
    fatigue_cost = c.fatigue_cost,
    technical_complexity = c.technical_complexity,
    stability_requirement = c.stability_requirement,
    tracking_type = c.tracking_type,
    load_convention = c.load_convention,
    strength_score = c.strength_score,
    hypertrophy_score = c.hypertrophy_score,
    general_fitness_score = c.general_fitness_score,
    approved_for_generation = true,
    updated_at = now()
from curated c
where e.source = 'free-exercise-db-with-videos'
  and e.source_id = c.source_id;

with translations(source_id, name_it) as (
    values
        ('1435','Squat con bilanciere'),
        ('0025','Panca piana con bilanciere'),
        ('0334','Alzate laterali con manubri'),
        ('0464','Plank frontale'),
        ('0553','Military press'),
        ('0198','Lat pulldown al cavo'),
        ('0314','Distensioni con manubri su panca inclinata'),
        ('0208','Rematore al cavo da seduto'),
        ('1723','Pushdown tricipiti al cavo'),
        ('0289','Shoulder press con manubri da seduto')
)
insert into public.exercise_translations (
    exercise_id,
    language,
    name
)
select e.id, 'it', t.name_it
from translations t
join public.exercises e
  on e.source = 'free-exercise-db-with-videos'
 and e.source_id = t.source_id
on conflict (exercise_id, language) do update
set
    name = excluded.name,
    updated_at = now();

update public.strength_workout_exercises swe
set exercise_id = e.id
from public.exercises e
where swe.exercise_id is null
  and e.legacy_key = swe.exercise_key;
