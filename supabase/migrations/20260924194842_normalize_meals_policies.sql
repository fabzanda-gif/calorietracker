-- Applied remotely as Supabase migration 20260924194842_normalize_meals_policies

drop policy if exists "Authenticated users can read shared meals" on public.meals;
drop policy if exists "Isolamento meals" on public.meals;

create policy meals_select_own_or_shared
on public.meals for select
to authenticated
using (((select auth.uid()) = user_id) or is_shared = true);

create policy meals_insert_own
on public.meals for insert
to authenticated
with check ((select auth.uid()) = user_id);

create policy meals_update_own
on public.meals for update
to authenticated
using ((select auth.uid()) = user_id)
with check ((select auth.uid()) = user_id);

create policy meals_delete_own
on public.meals for delete
to authenticated
using ((select auth.uid()) = user_id);
