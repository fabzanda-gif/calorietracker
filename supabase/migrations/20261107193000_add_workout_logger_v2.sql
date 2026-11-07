alter table public.strength_workouts
    alter column strength_plan_id drop not null,
    alter column training_week drop not null,
    alter column workout_index drop not null;

alter table public.strength_workouts
    drop constraint if exists strength_workouts_focus_check;

alter table public.strength_workouts
    add constraint strength_workouts_focus_check
    check (
        focus in (
            'full_body',
            'upper',
            'lower',
            'push',
            'pull',
            'legs',
            'free'
        )
    );

alter table public.strength_workouts
    add column if not exists workout_kind text not null default 'planned'
        check (workout_kind in ('planned', 'free'));

update public.strength_workouts
set workout_kind = 'planned'
where workout_kind is null;

alter table public.strength_workout_exercises
    alter column movement_pattern drop not null;

alter table public.strength_workout_exercises
    add column if not exists is_user_added boolean not null default false,
    add column if not exists substituted_from_exercise_id uuid null
        references public.exercises(id)
        on delete set null,
    add column if not exists prescription_source text not null default 'plan'
        check (
            prescription_source in (
                'plan',
                'manual',
                'substitution'
            )
        );

create index if not exists strength_workout_exercises_substituted_from_idx
    on public.strength_workout_exercises(substituted_from_exercise_id)
    where substituted_from_exercise_id is not null;

alter table public.strength_workout_logs
    add column if not exists status text not null default 'completed'
        check (status in ('draft', 'completed')),
    add column if not exists started_at timestamptz null,
    add column if not exists completed_at timestamptz null;

update public.strength_workout_logs
set
    status = 'completed',
    started_at = coalesce(started_at, created_at),
    completed_at = coalesce(completed_at, updated_at, created_at)
where status = 'completed';

alter table public.strength_set_logs
    add column if not exists feeling text null
        check (
            feeling is null
            or feeling in (
                'easy',
                'right',
                'hard',
                'too_hard'
            )
        ),
    add column if not exists updated_at timestamptz not null default now();

drop policy if exists "strength_workout_logs_update_own"
    on public.strength_workout_logs;
create policy "strength_workout_logs_update_own"
    on public.strength_workout_logs
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "strength_set_logs_update_own"
    on public.strength_set_logs;
create policy "strength_set_logs_update_own"
    on public.strength_set_logs
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);

drop policy if exists "strength_set_logs_delete_own"
    on public.strength_set_logs;
create policy "strength_set_logs_delete_own"
    on public.strength_set_logs
    for delete
    to authenticated
    using ((select auth.uid()) = user_id);

create index if not exists strength_workouts_kind_date_idx
    on public.strength_workouts(user_id, workout_kind, scheduled_date);

create index if not exists strength_workout_logs_status_idx
    on public.strength_workout_logs(user_id, status, performed_date);
