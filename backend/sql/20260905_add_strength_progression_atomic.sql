create or replace function
public.apply_strength_progression_atomic(
    p_user_id uuid,
    p_strength_plan_id uuid,
    p_source_workout_id uuid,
    p_source_exercise_id uuid,
    p_target_workout_id uuid,
    p_target_exercise_id uuid,
    p_exercise_key text,
    p_outcome text,
    p_action text,
    p_observed_load_kg numeric,
    p_expected_before_load_kg numeric,
    p_after_load_kg numeric
)
returns jsonb
language plpgsql
security invoker
set search_path = public
as $$
declare
    v_target
        public.strength_workout_exercises%rowtype;

    v_history
        public.strength_progression_history%rowtype;
begin
    if auth.uid() is distinct from p_user_id then
        raise exception 'not_authorized'
            using errcode = '42501';
    end if;

    select e.*
    into v_target
    from public.strength_workout_exercises e
    join public.strength_workouts w
        on w.id = e.strength_workout_id
    where e.id = p_target_exercise_id
      and e.user_id = p_user_id
      and w.id = p_target_workout_id
      and w.user_id = p_user_id
      and w.strength_plan_id = p_strength_plan_id
      and w.status = 'planned'
    for update of e;

    if not found then
        return jsonb_build_object(
            'applied', false,
            'reason', 'target_not_available'
        );
    end if;

    if v_target.exercise_key
        is distinct from p_exercise_key
    then
        return jsonb_build_object(
            'applied', false,
            'reason', 'exercise_key_mismatch'
        );
    end if;

    if v_target.prescribed_load_kg
        is distinct from
            p_expected_before_load_kg
    then
        return jsonb_build_object(
            'applied', false,
            'reason', 'stale_target',
            'current_load_kg',
                v_target.prescribed_load_kg
        );
    end if;

    if exists (
        select 1
        from public.strength_progression_history h
        where h.user_id = p_user_id
          and h.source_exercise_id =
              p_source_exercise_id
    ) then
        return jsonb_build_object(
            'applied', false,
            'reason', 'source_already_handled'
        );
    end if;

    if exists (
        select 1
        from public.strength_progression_history h
        where h.user_id = p_user_id
          and h.target_exercise_id =
              p_target_exercise_id
    ) then
        return jsonb_build_object(
            'applied', false,
            'reason', 'target_already_handled'
        );
    end if;

    insert into
        public.strength_progression_history (
            user_id,
            strength_plan_id,
            source_workout_id,
            source_exercise_id,
            target_workout_id,
            target_exercise_id,
            exercise_key,
            outcome,
            action,
            observed_load_kg,
            before_load_kg,
            after_load_kg
        )
    values (
        p_user_id,
        p_strength_plan_id,
        p_source_workout_id,
        p_source_exercise_id,
        p_target_workout_id,
        p_target_exercise_id,
        p_exercise_key,
        p_outcome,
        p_action,
        p_observed_load_kg,
        p_expected_before_load_kg,
        p_after_load_kg
    )
    returning *
    into v_history;

    update
        public.strength_workout_exercises
    set
        prescribed_load_kg = p_after_load_kg
    where id = p_target_exercise_id
      and user_id = p_user_id
    returning *
    into v_target;

    if not found then
        raise exception
            'strength progression target disappeared';
    end if;

    return jsonb_build_object(
        'applied', true,
        'history', to_jsonb(v_history),
        'target_exercise', to_jsonb(v_target)
    );

exception
    when unique_violation then
        return jsonb_build_object(
            'applied', false,
            'reason', 'concurrent_conflict'
        );
end;
$$;

revoke all on function
public.apply_strength_progression_atomic(
    uuid,
    uuid,
    uuid,
    uuid,
    uuid,
    uuid,
    text,
    text,
    text,
    numeric,
    numeric,
    numeric
)
from public;

grant execute on function
public.apply_strength_progression_atomic(
    uuid,
    uuid,
    uuid,
    uuid,
    uuid,
    uuid,
    text,
    text,
    text,
    numeric,
    numeric,
    numeric
)
to authenticated;
