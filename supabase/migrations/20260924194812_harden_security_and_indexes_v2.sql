-- Applied remotely as Supabase migration 20260924194812_harden_security_and_indexes_v2
-- Production hardening for SanoSync.

alter table public.activities enable row level security;
alter table public.google_calendar_connections enable row level security;
alter table public.google_calendar_events enable row level security;

drop policy if exists "Permetti tutto agli utenti anonimi su recipes" on public.recipes;
drop policy if exists "Permetti tutto agli utenti anonimi su daily_logs" on public.daily_logs;

revoke all privileges on table public.google_calendar_connections from anon, authenticated;

drop policy if exists google_calendar_events_select_own on public.google_calendar_events;
drop policy if exists google_calendar_events_insert_own on public.google_calendar_events;
drop policy if exists google_calendar_events_update_own on public.google_calendar_events;
drop policy if exists google_calendar_events_delete_own on public.google_calendar_events;

create policy google_calendar_events_select_own
on public.google_calendar_events for select
to authenticated
using ((select auth.uid()) = user_id);

create policy google_calendar_events_insert_own
on public.google_calendar_events for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy google_calendar_events_update_own
on public.google_calendar_events for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy google_calendar_events_delete_own
on public.google_calendar_events for delete
to authenticated
using ((select auth.uid()) = user_id);

do $$
declare
  p record;
  new_using text;
  new_check text;
  sql text;
begin
  for p in
    select schemaname, tablename, policyname, cmd, qual, with_check
    from pg_policies
    where schemaname = 'public'
      and (
        coalesce(qual, '') like '%auth.uid()%'
        or coalesce(with_check, '') like '%auth.uid()%'
      )
  loop
    new_using := case
      when p.qual is null then null
      else replace(p.qual, 'auth.uid()', '(select auth.uid())')
    end;
    new_check := case
      when p.with_check is null then null
      else replace(p.with_check, 'auth.uid()', '(select auth.uid())')
    end;

    if p.cmd = 'INSERT' then
      sql := format(
        'alter policy %I on %I.%I to authenticated with check (%s)',
        p.policyname, p.schemaname, p.tablename, new_check
      );
    elsif p.cmd in ('SELECT', 'DELETE') then
      sql := format(
        'alter policy %I on %I.%I to authenticated using (%s)',
        p.policyname, p.schemaname, p.tablename, new_using
      );
    elsif p.cmd in ('UPDATE', 'ALL') then
      sql := format(
        'alter policy %I on %I.%I to authenticated using (%s) with check (%s)',
        p.policyname,
        p.schemaname,
        p.tablename,
        new_using,
        coalesce(new_check, new_using)
      );
    else
      continue;
    end if;

    execute sql;
  end loop;
end
$$;

alter function public.generate_daily_summary(date)
  set search_path = pg_catalog;

revoke all on function public.generate_daily_summary(date) from public;
revoke all on function public.generate_daily_summary(date) from anon;
revoke all on function public.generate_daily_summary(date) from authenticated;

alter default privileges for role postgres in schema public
  revoke select, insert, update, delete on tables from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke execute on functions from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke usage, select on sequences from anon, authenticated, service_role;
alter default privileges for role postgres in schema public
  revoke execute on functions from public;

alter table public.daily_logs
  drop constraint if exists daily_logs_user_id_date_key;

create index if not exists meal_prep_batches_recipe_id_idx
  on public.meal_prep_batches (recipe_id);

create index if not exists strength_progression_history_source_exercise_id_idx
  on public.strength_progression_history (source_exercise_id);
create index if not exists strength_progression_history_source_workout_id_idx
  on public.strength_progression_history (source_workout_id);
create index if not exists strength_progression_history_strength_plan_id_idx
  on public.strength_progression_history (strength_plan_id);
create index if not exists strength_progression_history_target_exercise_id_idx
  on public.strength_progression_history (target_exercise_id);
create index if not exists strength_progression_history_target_workout_id_idx
  on public.strength_progression_history (target_workout_id);

create index if not exists strength_workout_exercises_user_id_idx
  on public.strength_workout_exercises (user_id);

create index if not exists training_plan_adaptations_source_planned_activity_id_idx
  on public.training_plan_adaptations (source_planned_activity_id);
create index if not exists training_plan_adaptations_target_planned_activity_id_idx
  on public.training_plan_adaptations (target_planned_activity_id);
