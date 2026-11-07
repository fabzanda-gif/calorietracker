create index if not exists exercises_family_id_idx
    on public.exercises(family_id)
    where family_id is not null;

create index if not exists exercises_replaced_by_idx
    on public.exercises(replaced_by)
    where replaced_by is not null;

create index if not exists muscles_parent_id_idx
    on public.muscles(parent_id)
    where parent_id is not null;

create index if not exists exercise_relationships_target_idx
    on public.exercise_relationships(target_exercise_id);
