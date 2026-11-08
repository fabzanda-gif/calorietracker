create table public.strength_load_profiles (
  user_id uuid not null references auth.users(id) on delete cascade,
  exercise_ref text not null check (length(exercise_ref) between 1 and 300),
  exercise_name text not null check (length(exercise_name) between 1 and 300),
  one_rep_max_kg numeric check (one_rep_max_kg > 0 and one_rep_max_kg <= 2000),
  working_load_kg numeric not null check (working_load_kg >= 0 and working_load_kg <= 1000),
  reference_reps integer not null check (reference_reps between 1 and 30),
  reserve_reps integer not null check (reserve_reps between 0 and 10),
  source text not null check (source in ('known_max', 'guided_test')),
  updated_at timestamptz not null default now(),
  primary key (user_id, exercise_ref)
);
alter table public.strength_load_profiles enable row level security;
revoke all on public.strength_load_profiles from anon;
grant select, insert, update, delete on public.strength_load_profiles to authenticated;
grant all on public.strength_load_profiles to service_role;
create policy strength_load_profiles_select on public.strength_load_profiles for select to authenticated using ((select auth.uid()) = user_id);
create policy strength_load_profiles_insert on public.strength_load_profiles for insert to authenticated with check ((select auth.uid()) = user_id);
create policy strength_load_profiles_update on public.strength_load_profiles for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy strength_load_profiles_delete on public.strength_load_profiles for delete to authenticated using ((select auth.uid()) = user_id);
