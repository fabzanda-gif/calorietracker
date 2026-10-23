alter table public.activities
    add column if not exists planned_activity_id uuid;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'activities_planned_activity_id_fkey'
    ) then
        alter table public.activities
            add constraint activities_planned_activity_id_fkey
            foreign key (planned_activity_id)
            references public.planned_activities(id)
            on delete set null;
    end if;
end
$$;

create unique index if not exists
    activities_planned_activity_id_unique_idx
    on public.activities(planned_activity_id)
    where planned_activity_id is not null;
