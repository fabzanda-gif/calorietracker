-- Phase 1 — user-specific exercise preferences from the modular Training Profile.
-- No exercise library approval or workout modification.
create table if not exists public.training_exercise_preferences (
    user_id uuid not null references auth.users(id) on delete cascade,
    exercise_id uuid not null references public.exercises(id) on delete cascade,
    preference text not null check (preference in ('preferred','excluded')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, exercise_id)
);

create index if not exists training_exercise_preferences_exercise_idx
    on public.training_exercise_preferences(exercise_id);

alter table public.training_exercise_preferences enable row level security;

revoke all on public.training_exercise_preferences from anon, authenticated;
grant select, insert, update, delete on public.training_exercise_preferences to authenticated;
grant select, insert, update, delete on public.training_exercise_preferences to service_role;

create policy "training_exercise_preferences_select_own"
    on public.training_exercise_preferences for select to authenticated
    using ((select auth.uid()) = user_id);
create policy "training_exercise_preferences_insert_own"
    on public.training_exercise_preferences for insert to authenticated
    with check ((select auth.uid()) = user_id);
create policy "training_exercise_preferences_update_own"
    on public.training_exercise_preferences for update to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
create policy "training_exercise_preferences_delete_own"
    on public.training_exercise_preferences for delete to authenticated
    using ((select auth.uid()) = user_id);
