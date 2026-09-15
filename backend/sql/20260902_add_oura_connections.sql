create table if not exists public.oura_connections (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null unique
        references auth.users(id) on delete cascade,
    access_token text not null,
    refresh_token text not null,
    token_type text not null default 'bearer',
    scope text,
    expires_at timestamptz,
    oura_user_id text,
    connected_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_synced_at timestamptz
);

alter table public.oura_connections
    enable row level security;

revoke all on table public.oura_connections
    from anon, authenticated;

grant all on table public.oura_connections
    to service_role;

create index if not exists
    oura_connections_user_id_idx
    on public.oura_connections(user_id);
