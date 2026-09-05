alter table public.activities
    add column if not exists estimated_steps integer;

alter table public.activities
    drop constraint if exists activities_estimated_steps_check;

alter table public.activities
    add constraint activities_estimated_steps_check
    check (
        estimated_steps is null
        or estimated_steps >= 0
    );
