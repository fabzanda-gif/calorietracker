create table if not exists public.training_plan_adaptations (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    training_plan_id uuid not null
        references public.training_plans(id)
        on delete cascade,

    source_planned_activity_id uuid
        references public.planned_activities(id)
        on delete set null,

    target_planned_activity_id uuid
        references public.planned_activities(id)
        on delete set null,

    outcome text not null
        check (
            outcome in (
                'on_target',
                'under',
                'over',
                'skipped',
                'unmatched'
            )
        ),

    recommended_action text not null
        check (
            recommended_action in (
                'keep_plan',
                'ease_next',
                'recover_next',
                'review'
            )
        ),

    decision text not null
        check (
            decision in (
                'applied',
                'kept'
            )
        ),

    load_ratio numeric null,

    title text null,
    message text null,

    proposed_changes jsonb not null
        default '{}'::jsonb,

    before_state jsonb null,
    after_state jsonb null,

    created_at timestamptz not null
        default now()
);

create index if not exists
    training_plan_adaptations_plan_created_idx
on public.training_plan_adaptations (
    training_plan_id,
    created_at desc
);

create index if not exists
    training_plan_adaptations_user_created_idx
on public.training_plan_adaptations (
    user_id,
    created_at desc
);

alter table public.training_plan_adaptations
    enable row level security;

drop policy if exists
    "training_plan_adaptations_select_own"
on public.training_plan_adaptations;

create policy
    "training_plan_adaptations_select_own"
on public.training_plan_adaptations
for select
using (auth.uid() = user_id);

drop policy if exists
    "training_plan_adaptations_insert_own"
on public.training_plan_adaptations;

create policy
    "training_plan_adaptations_insert_own"
on public.training_plan_adaptations
for insert
with check (auth.uid() = user_id);
