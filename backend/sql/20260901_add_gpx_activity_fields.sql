-- Estende le attività esistenti con dati GPX opzionali.
-- Le attività manuali continuano a funzionare senza modifiche.

alter table public.activities
    add column if not exists source text
        not null default 'manual',
    add column if not exists activity_type text,
    add column if not exists started_at timestamptz,
    add column if not exists duration_seconds integer,
    add column if not exists distance_meters numeric,
    add column if not exists average_cadence numeric,
    add column if not exists average_heart_rate numeric,
    add column if not exists route_points jsonb
        not null default '[]'::jsonb,
    add column if not exists series_points jsonb
        not null default '[]'::jsonb,
    add column if not exists original_point_count integer,
    add column if not exists gpx_file_name text;

alter table public.activities
    drop constraint if exists activities_source_check;

alter table public.activities
    add constraint activities_source_check
    check (source in ('manual', 'gpx'));

alter table public.activities
    drop constraint if exists activities_duration_seconds_check;

alter table public.activities
    add constraint activities_duration_seconds_check
    check (
        duration_seconds is null
        or duration_seconds >= 0
    );

alter table public.activities
    drop constraint if exists activities_distance_meters_check;

alter table public.activities
    add constraint activities_distance_meters_check
    check (
        distance_meters is null
        or distance_meters >= 0
    );

create index if not exists activities_user_date_index
    on public.activities (user_id, date desc);
