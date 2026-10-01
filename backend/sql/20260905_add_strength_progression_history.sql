create table if not exists
public.strength_progression_history (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    strength_plan_id uuid not null
        references public.strength_plans(id)
        on delete cascade,

    source_workout_id uuid not null
        references public.strength_workouts(id)
        on delete cascade,

    source_exercise_id uuid not null
        references public.strength_workout_exercises(id)
        on delete cascade,

    target_workout_id uuid not null
        references public.strength_workouts(id)
        on delete cascade,

    target_exercise_id uuid not null
        references public.strength_workout_exercises(id)
        on delete cascade,

    exercise_key text not null,

    outcome text not null
        check (
            outcome in (
                'under_target',
                'on_target',
                'over_target'
            )
        ),

    action text not null
        check (
            action in (
                'increase_load',
                'maintain',
                'reduce_load'
            )
        ),

    observed_load_kg numeric null
        check (
            observed_load_kg is null
            or observed_load_kg >= 0
        ),

    before_load_kg numeric null
        check (
            before_load_kg is null
            or before_load_kg >= 0
        ),

    after_load_kg numeric null
        check (
            after_load_kg is null
            or after_load_kg >= 0
        ),

    created_at timestamptz not null
        default now(),

    constraint
        strength_progression_source_unique
        unique (
            user_id,
            source_exercise_id
        ),

    constraint
        strength_progression_target_unique
        unique (
            user_id,
            target_exercise_id
        )
);

create index if not exists
    strength_progression_history_plan_idx
on public.strength_progression_history(
    user_id,
    strength_plan_id,
    created_at desc
);

alter table
    public.strength_progression_history
enable row level security;

drop policy if exists
    "strength_progression_history_select_own"
on public.strength_progression_history;

create policy
    "strength_progression_history_select_own"
on public.strength_progression_history
for select
using (
    auth.uid() = user_id
);

drop policy if exists
    "strength_progression_history_insert_own"
on public.strength_progression_history;

create policy
    "strength_progression_history_insert_own"
on public.strength_progression_history
for insert
with check (
    auth.uid() = user_id
);

drop policy if exists
    "strength_progression_history_delete_own"
on public.strength_progression_history;

create policy
    "strength_progression_history_delete_own"
on public.strength_progression_history
for delete
using (
    auth.uid() = user_id
);
