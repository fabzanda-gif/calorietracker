create table if not exists public.day_briefings (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    date date not null,
    moment text not null check (moment in ('morning', 'afternoon', 'evening')),
    mode text not null check (mode in ('standard', 'zero')),
    input_signature text not null,
    message text not null,
    source text not null check (source in ('ai', 'fallback')),
    updated_at timestamptz not null default now(),
    unique (user_id, date, moment, mode)
);

alter table public.day_briefings enable row level security;

drop policy if exists "Users manage own day briefings" on public.day_briefings;
create policy "Users manage own day briefings"
    on public.day_briefings
    for all
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

notify pgrst, 'reload schema';
