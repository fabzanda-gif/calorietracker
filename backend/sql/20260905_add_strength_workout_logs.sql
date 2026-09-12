create table if not exists public.strength_workout_logs (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    strength_workout_id uuid not null
        references public.strength_workouts(id)
        on delete cascade,

    performed_date date not null,

    duration_minutes integer null
        check (
            duration_minutes is null
            or duration_minutes > 0
        ),

    notes text null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint strength_workout_logs_workout_unique
        unique (
            strength_workout_id
        )
);

create index if not exists
    strength_workout_logs_user_date_idx
on public.strength_workout_logs(
    user_id,
    performed_date
);

alter table public.strength_workout_logs
    enable row level security;

drop policy if exists
    "strength_workout_logs_select_own"
on public.strength_workout_logs;

create policy
    "strength_workout_logs_select_own"
on public.strength_workout_logs
for select
using (
    auth.uid() = user_id
);

drop policy if exists
    "strength_workout_logs_insert_own"
on public.strength_workout_logs;

create policy
    "strength_workout_logs_insert_own"
on public.strength_workout_logs
for insert
with check (
    auth.uid() = user_id
);

drop policy if exists
    "strength_workout_logs_delete_own"
on public.strength_workout_logs;

create policy
    "strength_workout_logs_delete_own"
on public.strength_workout_logs
for delete
using (
    auth.uid() = user_id
);


create table if not exists public.strength_set_logs (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    strength_workout_log_id uuid not null
        references public.strength_workout_logs(id)
        on delete cascade,

    strength_workout_exercise_id uuid not null
        references public.strength_workout_exercises(id)
        on delete cascade,

    set_index integer not null
        check (
            set_index > 0
        ),

    reps integer not null
        check (
            reps > 0
        ),

    load_kg numeric not null default 0
        check (
            load_kg >= 0
        ),

    rir numeric null
        check (
            rir is null
            or rir between 0 and 6
        ),

    created_at timestamptz not null default now(),

    constraint strength_set_logs_set_unique
        unique (
            strength_workout_log_id,
            strength_workout_exercise_id,
            set_index
        )
);

create index if not exists
    strength_set_logs_workout_log_idx
on public.strength_set_logs(
    strength_workout_log_id
);

create index if not exists
    strength_set_logs_exercise_idx
on public.strength_set_logs(
    strength_workout_exercise_id
);

alter table public.strength_set_logs
    enable row level security;

drop policy if exists
    "strength_set_logs_select_own"
on public.strength_set_logs;

create policy
    "strength_set_logs_select_own"
on public.strength_set_logs
for select
using (
    auth.uid() = user_id
);

drop policy if exists
    "strength_set_logs_insert_own"
on public.strength_set_logs;

create policy
    "strength_set_logs_insert_own"
on public.strength_set_logs
for insert
with check (
    auth.uid() = user_id
);
