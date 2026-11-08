-- Deploy before the API version that calls move_weight_atomic.
create or replace function public.move_weight_atomic(
    p_row_id integer,
    p_user_id uuid,
    p_new_date date,
    p_weight numeric
)
returns setof public.daily_logs
language plpgsql
security invoker
set search_path = ''
as $$
declare
    source_row public.daily_logs%rowtype;
    destination_row public.daily_logs%rowtype;
begin
    if auth.uid() is null or auth.uid() is distinct from p_user_id then
        raise exception 'not_authorized' using errcode = '42501';
    end if;
    if p_new_date is null or p_weight is null or p_weight <= 0
       or p_weight >= 'Infinity'::numeric then
        raise exception 'invalid_weight_or_date' using errcode = '22023';
    end if;

    -- Lock existing source/destination rows in a consistent order for moves
    -- in opposite directions. RLS and the explicit user predicate both apply.
    perform id from public.daily_logs
    where user_id = p_user_id and (id = p_row_id or date = p_new_date)
    order by id for update;

    select * into source_row from public.daily_logs
    where id = p_row_id and user_id = p_user_id and weight is not null;
    if not found then
        return;
    end if;

    insert into public.daily_logs (user_id, date, weight)
    values (p_user_id, p_new_date, p_weight)
    on conflict (user_id, date) do update set weight = excluded.weight
    returning * into destination_row;

    -- Same-day edits must not clear the newly saved measurement.
    if source_row.id <> destination_row.id then
        update public.daily_logs set weight = null
        where id = source_row.id and user_id = p_user_id;
    end if;
    return next destination_row;
end;
$$;

revoke all on function public.move_weight_atomic(integer, uuid, date, numeric)
from public, anon;
grant execute on function public.move_weight_atomic(integer, uuid, date, numeric)
to authenticated;
