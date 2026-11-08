-- Transactional smoke test: temporary reference, always rolled back.
begin;
select set_config('sanosync.test_owner', (select id::text from auth.users limit 1), true);
select set_config('request.jwt.claim.sub', current_setting('sanosync.test_owner'), true);
set local role authenticated;
do $$
begin
  insert into public.strength_load_profiles(user_id,exercise_ref,exercise_name,one_rep_max_kg,working_load_kg,reference_reps,reserve_reps,source)
  values(auth.uid(),'rls-transaction-test','RLS test',100,75,8,2,'known_max');
  if (select count(*) from public.strength_load_profiles where exercise_ref='rls-transaction-test') <> 1 then raise exception 'Owner cannot read own reference'; end if;
  update public.strength_load_profiles set working_load_kg=70 where exercise_ref='rls-transaction-test';
  if (select working_load_kg from public.strength_load_profiles where exercise_ref='rls-transaction-test') <> 70 then raise exception 'Owner cannot update reference'; end if;
end $$;
select set_config('request.jwt.claim.sub', gen_random_uuid()::text, true);
do $$
declare denied boolean := false; affected integer;
begin
  if exists(select 1 from public.strength_load_profiles where exercise_ref='rls-transaction-test') then raise exception 'Cross-user read allowed'; end if;
  update public.strength_load_profiles set working_load_kg=50 where exercise_ref='rls-transaction-test';
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Cross-user update allowed'; end if;
  delete from public.strength_load_profiles where exercise_ref='rls-transaction-test';
  get diagnostics affected = row_count;
  if affected <> 0 then raise exception 'Cross-user delete allowed'; end if;
  begin
    insert into public.strength_load_profiles(user_id,exercise_ref,exercise_name,working_load_kg,reference_reps,reserve_reps,source)
    values(current_setting('sanosync.test_owner')::uuid,'rls-transaction-foreign','RLS test',75,8,2,'guided_test');
  exception when insufficient_privilege then denied := true;
  end;
  if not denied then raise exception 'Cross-user insert allowed'; end if;
end $$;
rollback;
