create table if not exists public.strength_plans (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    goal text not null
        check (goal in (
            'hypertrophy',
            'strength',
            'general_fitness'
        )),

    experience_level text not null
        check (experience_level in (
            'beginner',
            'intermediate',
            'advanced'
        )),

    program_style text not null
        check (program_style in (
            'full_body',
            'upper_lower',
            'push_pull_legs'
        )),

    sessions_per_week integer not null
        check (sessions_per_week between 2 and 6),

    start_date date not null,

    total_weeks integer not null default 8
        check (total_weeks between 4 and 24),

    status text not null default 'active'
        check (status in (
            'active',
            'paused',
            'completed',
            'cancelled'
        )),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists strength_plans_user_status_idx
    on public.strength_plans(user_id, status);

alter table public.strength_plans
    enable row level security;

drop policy if exists "strength_plans_select_own"
    on public.strength_plans;

create policy "strength_plans_select_own"
    on public.strength_plans
    for select
    using (auth.uid() = user_id);

drop policy if exists "strength_plans_insert_own"
    on public.strength_plans;

create policy "strength_plans_insert_own"
    on public.strength_plans
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "strength_plans_update_own"
    on public.strength_plans;

create policy "strength_plans_update_own"
    on public.strength_plans
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "strength_plans_delete_own"
    on public.strength_plans;

create policy "strength_plans_delete_own"
    on public.strength_plans
    for delete
    using (auth.uid() = user_id);


create table if not exists public.strength_workouts (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    strength_plan_id uuid not null
        references public.strength_plans(id)
        on delete cascade,

    scheduled_date date not null,

    training_week integer not null
        check (training_week > 0),

    workout_index integer not null
        check (workout_index > 0),

    title text not null,

    focus text not null
        check (focus in (
            'full_body',
            'upper',
            'lower',
            'push',
            'pull',
            'legs'
        )),

    status text not null default 'planned'
        check (status in (
            'planned',
            'completed',
            'skipped'
        )),

    estimated_duration_minutes integer null
        check (
            estimated_duration_minutes is null
            or estimated_duration_minutes > 0
        ),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint strength_workouts_plan_week_index_unique
        unique (
            strength_plan_id,
            training_week,
            workout_index
        )
);

create index if not exists strength_workouts_user_date_idx
    on public.strength_workouts(user_id, scheduled_date);

create index if not exists strength_workouts_plan_idx
    on public.strength_workouts(
        strength_plan_id,
        training_week,
        workout_index
    );

alter table public.strength_workouts
    enable row level security;

drop policy if exists "strength_workouts_select_own"
    on public.strength_workouts;

create policy "strength_workouts_select_own"
    on public.strength_workouts
    for select
    using (auth.uid() = user_id);

drop policy if exists "strength_workouts_insert_own"
    on public.strength_workouts;

create policy "strength_workouts_insert_own"
    on public.strength_workouts
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "strength_workouts_update_own"
    on public.strength_workouts;

create policy "strength_workouts_update_own"
    on public.strength_workouts
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "strength_workouts_delete_own"
    on public.strength_workouts;

create policy "strength_workouts_delete_own"
    on public.strength_workouts
    for delete
    using (auth.uid() = user_id);


create table if not exists public.strength_workout_exercises (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    strength_workout_id uuid not null
        references public.strength_workouts(id)
        on delete cascade,

    position integer not null
        check (position > 0),

    exercise_key text not null,
    exercise_name text not null,

    movement_pattern text not null
        check (movement_pattern in (
            'squat',
            'hinge',
            'horizontal_push',
            'vertical_push',
            'horizontal_pull',
            'vertical_pull',
            'single_leg',
            'core',
            'isolation'
        )),

    target_sets integer not null
        check (target_sets between 1 and 10),

    target_reps_min integer not null
        check (target_reps_min > 0),

    target_reps_max integer not null,

    target_rir numeric null
        check (
            target_rir is null
            or target_rir between 0 and 6
        ),

    rest_seconds integer null
        check (
            rest_seconds is null
            or rest_seconds > 0
        ),

    prescribed_load_kg numeric null
        check (
            prescribed_load_kg is null
            or prescribed_load_kg >= 0
        ),

    created_at timestamptz not null default now(),

    constraint strength_workout_exercises_rep_range_check
        check (target_reps_max >= target_reps_min),

    constraint strength_workout_exercises_position_unique
        unique (
            strength_workout_id,
            position
        )
);

create index if not exists
    strength_workout_exercises_workout_idx
on public.strength_workout_exercises(
    strength_workout_id,
    position
);

alter table public.strength_workout_exercises
    enable row level security;

drop policy if exists "strength_workout_exercises_select_own"
    on public.strength_workout_exercises;

create policy "strength_workout_exercises_select_own"
    on public.strength_workout_exercises
    for select
    using (auth.uid() = user_id);

drop policy if exists "strength_workout_exercises_insert_own"
    on public.strength_workout_exercises;

create policy "strength_workout_exercises_insert_own"
    on public.strength_workout_exercises
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "strength_workout_exercises_update_own"
    on public.strength_workout_exercises;

create policy "strength_workout_exercises_update_own"
    on public.strength_workout_exercises
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "strength_workout_exercises_delete_own"
    on public.strength_workout_exercises;

create policy "strength_workout_exercises_delete_own"
    on public.strength_workout_exercises
    for delete
    using (auth.uid() = user_id);
