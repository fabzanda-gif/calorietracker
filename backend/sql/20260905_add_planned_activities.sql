create table if not exists public.planned_activities (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,

    scheduled_date date not null,
    scheduled_time time null,

    title text not null check (length(trim(title)) > 0),
    activity_type text not null check (length(trim(activity_type)) > 0),

    duration_minutes integer null
        check (duration_minutes is null or duration_minutes > 0),

    distance_meters numeric null
        check (distance_meters is null or distance_meters >= 0),

    intensity text not null default 'moderate'
        check (intensity in ('low', 'moderate', 'hard', 'race', 'unknown')),

    notes text null,

    status text not null default 'planned'
        check (status in ('planned', 'completed', 'skipped')),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists planned_activities_user_date_idx
    on public.planned_activities(user_id, scheduled_date);

alter table public.planned_activities enable row level security;

drop policy if exists "planned_activities_select_own"
    on public.planned_activities;

create policy "planned_activities_select_own"
    on public.planned_activities
    for select
    using (auth.uid() = user_id);

drop policy if exists "planned_activities_insert_own"
    on public.planned_activities;

create policy "planned_activities_insert_own"
    on public.planned_activities
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "planned_activities_update_own"
    on public.planned_activities;

create policy "planned_activities_update_own"
    on public.planned_activities
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "planned_activities_delete_own"
    on public.planned_activities;

create policy "planned_activities_delete_own"
    on public.planned_activities
    for delete
    using (auth.uid() = user_id);
