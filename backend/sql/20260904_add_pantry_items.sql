create table if not exists public.pantry_items (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references auth.users(id) on delete cascade,
    ingredient_id uuid not null references public.ingredients(id) on delete cascade,
    quantity numeric not null check (quantity > 0),
    unit text not null check (length(trim(unit)) > 0),
    expires_at date null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists pantry_items_user_id_idx
    on public.pantry_items(user_id);

create index if not exists pantry_items_ingredient_id_idx
    on public.pantry_items(ingredient_id);

create index if not exists pantry_items_expires_at_idx
    on public.pantry_items(expires_at);

alter table public.pantry_items enable row level security;

drop policy if exists "pantry_items_select_own"
    on public.pantry_items;

create policy "pantry_items_select_own"
    on public.pantry_items
    for select
    using (auth.uid() = user_id);

drop policy if exists "pantry_items_insert_own"
    on public.pantry_items;

create policy "pantry_items_insert_own"
    on public.pantry_items
    for insert
    with check (auth.uid() = user_id);

drop policy if exists "pantry_items_update_own"
    on public.pantry_items;

create policy "pantry_items_update_own"
    on public.pantry_items
    for update
    using (auth.uid() = user_id)
    with check (auth.uid() = user_id);

drop policy if exists "pantry_items_delete_own"
    on public.pantry_items;

create policy "pantry_items_delete_own"
    on public.pantry_items
    for delete
    using (auth.uid() = user_id);
