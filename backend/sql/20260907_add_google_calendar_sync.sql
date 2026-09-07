create table if not exists public.google_calendar_connections (
    user_id uuid primary key
        references auth.users(id)
        on delete cascade,

    access_token text not null,
    refresh_token text,
    token_type text,
    scope text,
    expires_at timestamptz,

    calendar_id text not null default 'primary',

    connected_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_synced_at timestamptz
);

create table if not exists public.google_calendar_events (
    id uuid primary key default gen_random_uuid(),

    user_id uuid not null
        references auth.users(id)
        on delete cascade,

    source_type text not null
        check (
            source_type in (
                'planned_activity',
                'strength_workout'
            )
        ),

    source_id uuid not null,

    google_event_id text not null,
    google_calendar_id text not null default 'primary',

    last_synced_at timestamptz not null default now(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),

    unique (user_id, source_type, source_id),
    unique (user_id, google_calendar_id, google_event_id)
);

create index if not exists
    google_calendar_events_user_idx
    on public.google_calendar_events(user_id);

create index if not exists
    google_calendar_events_source_idx
    on public.google_calendar_events(
        user_id,
        source_type,
        source_id
    );
