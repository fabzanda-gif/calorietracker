create table if not exists public.training_coach_preferences (
    user_id uuid primary key
        references auth.users(id)
        on delete cascade,

    priority text not null default 'balanced'
        check (
            priority in (
                'gym',
                'balanced',
                'running'
            )
        ),

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.training_coach_preferences
    enable row level security;

revoke all on table public.training_coach_preferences
    from anon, authenticated;

grant select, insert, update
    on public.training_coach_preferences
    to authenticated;

grant all
    on public.training_coach_preferences
    to service_role;

drop policy if exists
    "training_coach_preferences_select_own"
on public.training_coach_preferences;

create policy
    "training_coach_preferences_select_own"
on public.training_coach_preferences
for select
to authenticated
using ((select auth.uid()) = user_id);

drop policy if exists
    "training_coach_preferences_insert_own"
on public.training_coach_preferences;

create policy
    "training_coach_preferences_insert_own"
on public.training_coach_preferences
for insert
to authenticated
with check ((select auth.uid()) = user_id);

drop policy if exists
    "training_coach_preferences_update_own"
on public.training_coach_preferences;

create policy
    "training_coach_preferences_update_own"
on public.training_coach_preferences
for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);
