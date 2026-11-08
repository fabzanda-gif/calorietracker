-- Run in BEGIN/ROLLBACK after installing the quota migration in pg_temp:
-- replace public.ai_rate_limits with a TEMP table without the auth.users FK,
-- and public.consume_ai_rate_limit with pg_temp.consume_ai_rate_limit.
do $$
declare
    u uuid := '00000000-0000-0000-0000-000000000001';
    other_u uuid := '00000000-0000-0000-0000-000000000002';
    result jsonb;
begin
    assert not has_function_privilege('anon',
        'pg_temp.consume_ai_rate_limit(uuid,integer,integer)', 'EXECUTE');
    assert not has_function_privilege('authenticated',
        'pg_temp.consume_ai_rate_limit(uuid,integer,integer)', 'EXECUTE');
    assert has_function_privilege('service_role',
        'pg_temp.consume_ai_rate_limit(uuid,integer,integer)', 'EXECUTE');
    assert not has_table_privilege('authenticated','pg_temp.ai_rate_limits','UPDATE');

    assert (pg_temp.consume_ai_rate_limit(u,2,3)->>'allowed')::boolean;
    assert (pg_temp.consume_ai_rate_limit(u,2,3)->>'allowed')::boolean;
    result := pg_temp.consume_ai_rate_limit(u,2,3);
    assert not (result->>'allowed')::boolean;
    assert (result->>'retry_after')::integer between 1 and 60;
    assert (select cardinality(events) = 2 from pg_temp.ai_rate_limits where user_id = u);
    assert (pg_temp.consume_ai_rate_limit(other_u,2,3)->>'allowed')::boolean;

    update pg_temp.ai_rate_limits set events = array[
        clock_timestamp() - interval '2 minutes',
        clock_timestamp() - interval '2 minutes'
    ] where user_id = u;
    assert (pg_temp.consume_ai_rate_limit(u,2,3)->>'allowed')::boolean;
    result := pg_temp.consume_ai_rate_limit(u,2,3);
    assert not (result->>'allowed')::boolean;
    assert (result->>'retry_after')::integer between 86000 and 86400;

    update pg_temp.ai_rate_limits set events = array[
        clock_timestamp() - interval '25 hours'
    ] where user_id = u;
    assert (pg_temp.consume_ai_rate_limit(u,2,3)->>'allowed')::boolean;
    assert (select cardinality(events) = 1 from pg_temp.ai_rate_limits where user_id = u);
    begin
        perform pg_temp.consume_ai_rate_limit(u,0,3);
        raise exception 'Expected invalid limit rejection';
    exception when invalid_parameter_value then null;
    end;
end;
$$;
