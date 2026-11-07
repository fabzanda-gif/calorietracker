create table if not exists public.user_preferences (
    user_id uuid primary key
        references auth.users(id)
        on delete cascade,
    onboarding_version integer not null default 2
        check (onboarding_version >= 1),
    primary_goal text null
        check (
            primary_goal is null
            or primary_goal in (
                'hypertrophy',
                'strength',
                'general_fitness'
            )
        ),
    food_enabled boolean not null default false,
    training_enabled boolean not null default false,
    core_onboarding_completed boolean not null default false,
    food_setup_completed boolean not null default false,
    training_setup_completed boolean not null default false,
    last_step text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.nutrition_profiles (
    user_id uuid primary key
        references auth.users(id)
        on delete cascade,
    weight_strategy text null
        check (
            weight_strategy is null
            or weight_strategy in (
                'loss',
                'maintenance',
                'gain'
            )
        ),
    target_weight_kg numeric null
        check (
            target_weight_kg is null
            or target_weight_kg > 0
        ),
    calorie_adjustment_kcal numeric null
        check (
            calorie_adjustment_kcal is null
            or calorie_adjustment_kcal >= 0
        ),
    protein_target_mode text not null default 'automatic'
        check (
            protein_target_mode in (
                'automatic',
                'manual',
                'disabled'
            )
        ),
    protein_target_g numeric null
        check (
            protein_target_g is null
            or protein_target_g > 0
        ),
    macro_tracking_enabled boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.training_profiles (
    user_id uuid primary key
        references auth.users(id)
        on delete cascade,
    experience_level text not null
        check (
            experience_level in (
                'beginner',
                'intermediate',
                'advanced'
            )
        ),
    sessions_per_week integer not null
        check (sessions_per_week between 2 and 6),
    session_duration_minutes integer not null
        check (session_duration_minutes between 20 and 180),
    planning_horizon text not null
        check (planning_horizon in ('weekly', 'monthly')),
    environment text not null default 'commercial_gym'
        check (environment in ('commercial_gym')),
    coach_style text not null default 'balanced'
        check (
            coach_style in (
                'conservative',
                'balanced',
                'ambitious'
            )
        ),
    feedback_mode text not null default 'simple'
        check (feedback_mode in ('simple', 'advanced')),
    schedule_flexibility text not null default 'flexible'
        check (schedule_flexibility in ('fixed', 'flexible')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.training_preferred_days (
    user_id uuid not null
        references auth.users(id)
        on delete cascade,
    weekday integer not null
        check (weekday between 1 and 7),
    created_at timestamptz not null default now(),
    primary key (user_id, weekday)
);

create table if not exists public.training_muscle_priorities (
    user_id uuid not null
        references auth.users(id)
        on delete cascade,
    muscle_key text not null
        check (
            muscle_key in (
                'chest',
                'back',
                'shoulders',
                'biceps',
                'triceps',
                'glutes',
                'quadriceps',
                'hamstrings',
                'calves',
                'core'
            )
        ),
    created_at timestamptz not null default now(),
    primary key (user_id, muscle_key)
);

create index if not exists user_preferences_modules_idx
    on public.user_preferences(
        user_id,
        food_enabled,
        training_enabled
    );

alter table public.user_preferences enable row level security;
alter table public.nutrition_profiles enable row level security;
alter table public.training_profiles enable row level security;
alter table public.training_preferred_days enable row level security;
alter table public.training_muscle_priorities enable row level security;

revoke all on table public.user_preferences from anon, authenticated;
revoke all on table public.nutrition_profiles from anon, authenticated;
revoke all on table public.training_profiles from anon, authenticated;
revoke all on table public.training_preferred_days from anon, authenticated;
revoke all on table public.training_muscle_priorities from anon, authenticated;

grant select, insert, update, delete on table public.user_preferences to authenticated;
grant select, insert, update, delete on table public.nutrition_profiles to authenticated;
grant select, insert, update, delete on table public.training_profiles to authenticated;
grant select, insert, update, delete on table public.training_preferred_days to authenticated;
grant select, insert, update, delete on table public.training_muscle_priorities to authenticated;

grant select, insert, update, delete on table public.user_preferences to service_role;
grant select, insert, update, delete on table public.nutrition_profiles to service_role;
grant select, insert, update, delete on table public.training_profiles to service_role;
grant select, insert, update, delete on table public.training_preferred_days to service_role;
grant select, insert, update, delete on table public.training_muscle_priorities to service_role;

drop policy if exists "user_preferences_select_own" on public.user_preferences;
create policy "user_preferences_select_own"
    on public.user_preferences for select to authenticated
    using ((select auth.uid()) = user_id);
drop policy if exists "user_preferences_insert_own" on public.user_preferences;
create policy "user_preferences_insert_own"
    on public.user_preferences for insert to authenticated
    with check ((select auth.uid()) = user_id);
drop policy if exists "user_preferences_update_own" on public.user_preferences;
create policy "user_preferences_update_own"
    on public.user_preferences for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
drop policy if exists "user_preferences_delete_own" on public.user_preferences;
create policy "user_preferences_delete_own"
    on public.user_preferences for delete to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "nutrition_profiles_select_own" on public.nutrition_profiles;
create policy "nutrition_profiles_select_own"
    on public.nutrition_profiles for select to authenticated
    using ((select auth.uid()) = user_id);
drop policy if exists "nutrition_profiles_insert_own" on public.nutrition_profiles;
create policy "nutrition_profiles_insert_own"
    on public.nutrition_profiles for insert to authenticated
    with check ((select auth.uid()) = user_id);
drop policy if exists "nutrition_profiles_update_own" on public.nutrition_profiles;
create policy "nutrition_profiles_update_own"
    on public.nutrition_profiles for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
drop policy if exists "nutrition_profiles_delete_own" on public.nutrition_profiles;
create policy "nutrition_profiles_delete_own"
    on public.nutrition_profiles for delete to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "training_profiles_select_own" on public.training_profiles;
create policy "training_profiles_select_own"
    on public.training_profiles for select to authenticated
    using ((select auth.uid()) = user_id);
drop policy if exists "training_profiles_insert_own" on public.training_profiles;
create policy "training_profiles_insert_own"
    on public.training_profiles for insert to authenticated
    with check ((select auth.uid()) = user_id);
drop policy if exists "training_profiles_update_own" on public.training_profiles;
create policy "training_profiles_update_own"
    on public.training_profiles for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
drop policy if exists "training_profiles_delete_own" on public.training_profiles;
create policy "training_profiles_delete_own"
    on public.training_profiles for delete to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "training_preferred_days_select_own" on public.training_preferred_days;
create policy "training_preferred_days_select_own"
    on public.training_preferred_days for select to authenticated
    using ((select auth.uid()) = user_id);
drop policy if exists "training_preferred_days_insert_own" on public.training_preferred_days;
create policy "training_preferred_days_insert_own"
    on public.training_preferred_days for insert to authenticated
    with check ((select auth.uid()) = user_id);
drop policy if exists "training_preferred_days_delete_own" on public.training_preferred_days;
create policy "training_preferred_days_delete_own"
    on public.training_preferred_days for delete to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "training_muscle_priorities_select_own" on public.training_muscle_priorities;
create policy "training_muscle_priorities_select_own"
    on public.training_muscle_priorities for select to authenticated
    using ((select auth.uid()) = user_id);
drop policy if exists "training_muscle_priorities_insert_own" on public.training_muscle_priorities;
create policy "training_muscle_priorities_insert_own"
    on public.training_muscle_priorities for insert to authenticated
    with check ((select auth.uid()) = user_id);
drop policy if exists "training_muscle_priorities_delete_own" on public.training_muscle_priorities;
create policy "training_muscle_priorities_delete_own"
    on public.training_muscle_priorities for delete to authenticated
    using ((select auth.uid()) = user_id);

insert into public.user_preferences (
    user_id,
    onboarding_version,
    primary_goal,
    food_enabled,
    training_enabled,
    core_onboarding_completed,
    food_setup_completed,
    training_setup_completed,
    last_step
)
select
    u.id,
    1,
    null,
    true,
    false,
    true,
    true,
    false,
    'complete'
from auth.users u
where
    coalesce(u.raw_user_meta_data ->> 'gender', '') <> ''
    and coalesce(u.raw_user_meta_data ->> 'birth_date', '') <> ''
    and coalesce(u.raw_user_meta_data ->> 'height', '') <> ''
    and (
        coalesce(u.raw_user_meta_data ->> 'goal_mode', '') <> ''
        or coalesce(u.raw_user_meta_data ->> 'deficit_plan', '') <> ''
    )
on conflict (user_id) do nothing;

insert into public.user_preferences (
    user_id,
    onboarding_version,
    primary_goal,
    food_enabled,
    training_enabled,
    core_onboarding_completed,
    food_setup_completed,
    training_setup_completed,
    last_step
)
select distinct
    source.user_id,
    1,
    source.primary_goal,
    false,
    true,
    true,
    false,
    false,
    'training_setup'
from (
    select sp.user_id, sp.goal as primary_goal
    from public.strength_plans sp
    union all
    select tp.user_id, null::text as primary_goal
    from public.training_plans tp
) source
where source.user_id is not null
on conflict (user_id) do update
set
    training_enabled = true,
    updated_at = now();

update public.user_preferences
set
    last_step = case
        when training_enabled and not training_setup_completed
            then 'training_setup'
        else last_step
    end,
    updated_at = now()
where training_enabled = true;
