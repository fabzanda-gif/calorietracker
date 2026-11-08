-- Server-only rolling AI quotas. No client can read or reset these counters.
create table public.ai_rate_limits (
    user_id uuid primary key references auth.users(id) on delete cascade,
    events timestamptz[] not null default '{}'
);
alter table public.ai_rate_limits enable row level security;
revoke all on public.ai_rate_limits from public, anon, authenticated;
grant select, insert, update, delete on public.ai_rate_limits to service_role;

create function public.consume_ai_rate_limit(
    p_user_id uuid, p_minute_limit integer, p_day_limit integer
) returns jsonb
language plpgsql security invoker set search_path = '' as $$
declare
    event_times timestamptz[];
    minute_times timestamptz[];
    current_time_at_check timestamptz;
    retry integer;
begin
    if p_user_id is null or p_minute_limit < 1 or p_day_limit < p_minute_limit
       or p_minute_limit is null or p_day_limit is null then
        raise exception 'invalid_rate_limit' using errcode = '22023';
    end if;
    insert into public.ai_rate_limits (user_id) values (p_user_id)
    on conflict (user_id) do nothing;
    select events into event_times from public.ai_rate_limits
    where user_id = p_user_id for update;
    -- Take the clock AFTER waiting for the lock so concurrent calls cannot
    -- append out-of-order timestamps or reuse a stale time window.
    current_time_at_check := clock_timestamp();
    select coalesce(array_agg(t order by t), '{}') into event_times
    from unnest(event_times) t where t > current_time_at_check - interval '24 hours';
    select coalesce(array_agg(t order by t), '{}') into minute_times
    from unnest(event_times) t where t > current_time_at_check - interval '1 minute';
    if cardinality(event_times) >= p_day_limit then
        retry := greatest(1, ceil(extract(epoch from
            event_times[1] + interval '24 hours' - current_time_at_check))::integer);
    elsif cardinality(minute_times) >= p_minute_limit then
        retry := greatest(1, ceil(extract(epoch from
            minute_times[1] + interval '1 minute' - current_time_at_check))::integer);
    else
        update public.ai_rate_limits set events = array_append(event_times, current_time_at_check)
        where user_id = p_user_id;
        return jsonb_build_object('allowed', true, 'retry_after', 0);
    end if;
    update public.ai_rate_limits set events = event_times where user_id = p_user_id;
    return jsonb_build_object('allowed', false, 'retry_after', retry);
end;
$$;
revoke all on function public.consume_ai_rate_limit(uuid, integer, integer)
from public, anon, authenticated;
grant execute on function public.consume_ai_rate_limit(uuid, integer, integer)
to service_role;
