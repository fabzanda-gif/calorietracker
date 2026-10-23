alter table public.planned_activities
  add column if not exists suspended_by_special_period_id uuid references public.special_periods(id) on delete set null;

alter table public.planned_activities
  drop constraint if exists planned_activities_status_check;

alter table public.planned_activities
  add constraint planned_activities_status_check
  check (status = any (array['planned'::text, 'completed'::text, 'skipped'::text, 'suspended'::text]));

create index if not exists planned_activities_suspension_idx
  on public.planned_activities (suspended_by_special_period_id)
  where suspended_by_special_period_id is not null;
