create table if not exists public.training_plans (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,

    sport text not null default 'running'
        check (sport in ('running')),

    start_date date not null,
    target_date date not null,

    current_distance_meters numeric not null
        check (current_distance_meters > 0),

    current_pace_seconds_per_km integer not null
        check (current_pace_seconds_per_km > 0),

    target_distance_meters numeric not null
        check (target_distance_meters > 0),

    target_pace_seconds_per_km integer not null
        check (target_pace_seconds_per_km > 0),

    sessions_per_week integer not null
        check (sessions_per_week between 2 and 5),

    long_run_weekday integer not null default 6
        check (long_run_weekday between 0 and 6),

    total_weeks integer not null
        check (total_weeks > 0),

    status text not null default 'active'
        check (status in ('active', 'paused', 'completed', 'cancelled')),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists training_plans_user_idx
    on public.training_plans(user_id);

create index if not exists training_plans_user_status_idx
    on public.training_plans(user_id, status);

alter table public.training_plans enable row level security;

drop policy if exists "training_plans_select_own"
    on public.training_plans;

create policy "training_plans_select_own"
    on public.training_plans
    for select
    using (auth.uid() = user_id);

drop policy if exists "training_plans_insert_own"
    on public.training_plans;

create policy "training_plans_insert_own"
    on public.training_plans
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "training_plans_update_own"
    on public.training_plans;

create policy "training_plans_update_own"
    on public.training_plans
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "training_plans_delete_own"
    on public.training_plans;

create policy "training_plans_delete_own"
    on public.training_plans
    for delete
    using (auth.uid() = user_id);


alter table public.planned_activities
    add column if not exists training_plan_id uuid null
        references public.training_plans(id)
        on delete cascade;

alter table public.planned_activities
    add column if not exists training_week integer null
        check (training_week is null or training_week > 0);

alter table public.planned_activities
    add column if not exists session_kind text null
        check (
            session_kind is null
            or session_kind in (
                'easy',
                'recovery',
                'tempo',
                'interval',
                'long',
                'race'
            )
        );

create index if not exists planned_activities_training_plan_idx
    on public.planned_activities(training_plan_id);
