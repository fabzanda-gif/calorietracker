create table if not exists public.training_coach_adjustments (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    source_kind text not null
        check (source_kind in ('activity', 'strength_workout')),
    source_id text not null,
    source_date date not null,

    target_kind text not null
        check (target_kind in ('strength_workout', 'planned_activity')),
    target_id uuid not null,
    target_date date not null,

    action text not null
        check (
            action in (
                'reduce_load',
                'reduce_volume',
                'reduce_running_load',
                'reschedule'
            )
        ),
    severity text not null
        check (severity in ('low', 'moderate', 'high')),
    scope text not null
        check (
            scope in (
                'upper',
                'lower',
                'full_body',
                'cardio'
            )
        ),
    decision text not null
        check (
            decision in (
                'proposed',
                'auto_applied',
                'accepted',
                'dismissed'
            )
        ),

    title text not null,
    message text not null,

    proposed_changes jsonb not null default '{}'::jsonb,
    before_state jsonb null,
    after_state jsonb null,

    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    constraint training_coach_adjustments_unique_signal
        unique (
            user_id,
            source_kind,
            source_id,
            target_kind,
            target_id,
            action
        )
);

create index if not exists training_coach_adjustments_user_created_idx
    on public.training_coach_adjustments(
        user_id,
        created_at desc
    );

create index if not exists training_coach_adjustments_target_idx
    on public.training_coach_adjustments(
        user_id,
        target_kind,
        target_id
    );

create index if not exists training_coach_adjustments_pending_idx
    on public.training_coach_adjustments(
        user_id,
        decision,
        target_date
    );

alter table public.training_coach_adjustments
    enable row level security;

revoke all on table public.training_coach_adjustments
    from anon, authenticated;

grant select, insert, update
    on public.training_coach_adjustments
    to authenticated;

grant all
    on public.training_coach_adjustments
    to service_role;

drop policy if exists "training_coach_adjustments_select_own"
    on public.training_coach_adjustments;
create policy "training_coach_adjustments_select_own"
    on public.training_coach_adjustments
    for select
    to authenticated
    using ((select auth.uid()) = user_id);

drop policy if exists "training_coach_adjustments_insert_own"
    on public.training_coach_adjustments;
create policy "training_coach_adjustments_insert_own"
    on public.training_coach_adjustments
    for insert
    to authenticated
    with check ((select auth.uid()) = user_id);

drop policy if exists "training_coach_adjustments_update_own"
    on public.training_coach_adjustments;
create policy "training_coach_adjustments_update_own"
    on public.training_coach_adjustments
    for update
    to authenticated
    using ((select auth.uid()) = user_id)
    with check ((select auth.uid()) = user_id);
