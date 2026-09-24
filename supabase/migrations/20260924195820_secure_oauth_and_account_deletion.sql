-- Applied remotely as Supabase migration 20260924195820_secure_oauth_and_account_deletion

revoke all privileges on table public.oura_connections from anon, authenticated;

drop policy if exists oura_connections_select_own on public.oura_connections;
drop policy if exists oura_connections_insert_own on public.oura_connections;
drop policy if exists oura_connections_update_own on public.oura_connections;
drop policy if exists oura_connections_delete_own on public.oura_connections;

alter table public.activities
  drop constraint if exists activities_user_id_fkey;
alter table public.activities
  add constraint activities_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete cascade;

alter table public.daily_logs
  drop constraint if exists daily_logs_user_id_fkey;
alter table public.daily_logs
  add constraint daily_logs_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete cascade;

alter table public.meals
  drop constraint if exists meals_user_id_fkey;
alter table public.meals
  add constraint meals_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete cascade;

alter table public.recipes
  drop constraint if exists recipes_user_id_fkey;
alter table public.recipes
  add constraint recipes_user_id_fkey
  foreign key (user_id) references auth.users(id) on delete cascade;
