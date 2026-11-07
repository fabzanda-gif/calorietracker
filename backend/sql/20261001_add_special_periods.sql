create table if not exists public.special_periods (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  period_type text not null check (period_type in ('vacation','illness')),
  start_date date not null,
  end_date date not null,
  training_policy text not null check (training_policy in ('keep','suspend')),
  activity_bias text not null check (activity_bias in ('lower','normal','higher')),
  nutrition_mode text not null check (nutrition_mode in ('normal','flexible','recovery')),
  meal_context text not null check (meal_context in ('normal','out_of_routine')),
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint special_periods_date_range check (end_date >= start_date)
);

create index if not exists special_periods_user_dates_idx
  on public.special_periods (user_id, start_date, end_date);

alter table public.special_periods enable row level security;

grant select, insert, update, delete on table public.special_periods to authenticated;
grant select, insert, update, delete on table public.special_periods to service_role;

drop policy if exists "special periods select own" on public.special_periods;
create policy "special periods select own"
  on public.special_periods for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "special periods insert own" on public.special_periods;
create policy "special periods insert own"
  on public.special_periods for insert
  to authenticated
  with check (auth.uid() = user_id);

drop policy if exists "special periods update own" on public.special_periods;
create policy "special periods update own"
  on public.special_periods for update
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists "special periods delete own" on public.special_periods;
create policy "special periods delete own"
  on public.special_periods for delete
  to authenticated
  using (auth.uid() = user_id);
