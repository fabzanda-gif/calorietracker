-- Integration harness: run inside BEGIN/ROLLBACK after creating the migration's
-- function in pg_temp, replacing public.daily_logs with pg_temp.daily_logs.
-- It uses synthetic data only and never touches application tables.
select set_config('request.jwt.claim.sub', '00000000-0000-0000-0000-000000000001', true);

insert into pg_temp.daily_logs(id,user_id,date,weight,steps,notes)
values
    (1,'00000000-0000-0000-0000-000000000001','2026-11-01',75,8000,'source'),
    (2,'00000000-0000-0000-0000-000000000001','2026-11-02',76,9000,'destination'),
    (3,'00000000-0000-0000-0000-000000000002','2026-11-01',90,4000,'other user');

do $$
declare
    owner_id uuid := '00000000-0000-0000-0000-000000000001';
    other_id uuid := '00000000-0000-0000-0000-000000000002';
    moved pg_temp.daily_logs%rowtype;
begin
    select * into moved from pg_temp.move_weight_atomic(1,owner_id,'2026-11-02',74);
    assert moved.id = 2 and moved.weight = 74 and moved.steps = 9000;
    assert (select weight is null and steps = 8000 and notes = 'source'
            from pg_temp.daily_logs where id = 1);

    -- Same-day edit preserves the measurement.
    perform pg_temp.move_weight_atomic(2,owner_id,'2026-11-02',73);
    assert (select weight = 73 from pg_temp.daily_logs where id = 2);

    -- Unknown/foreign sources must not create or modify a destination.
    assert not exists(select * from pg_temp.move_weight_atomic(3,owner_id,'2026-11-03',80));
    assert not exists(select * from pg_temp.move_weight_atomic(999,owner_id,'2026-11-03',80));
    assert not exists(select 1 from pg_temp.daily_logs where date = '2026-11-03');
    assert (select weight = 90 from pg_temp.daily_logs where id = 3);

    begin
        perform pg_temp.move_weight_atomic(3,other_id,'2026-11-03',80);
        raise exception 'Expected authorization failure';
    exception when insufficient_privilege then null;
    end;

    -- Destination failure leaves the source intact.
    begin
        perform pg_temp.move_weight_atomic(2,owner_id,'2026-11-03',101);
        raise exception 'Expected destination constraint failure';
    exception when check_violation then null;
    end;
    assert (select weight = 73 from pg_temp.daily_logs where id = 2);
    assert not exists(select 1 from pg_temp.daily_logs where date = '2026-11-03');
end;
$$;

create function pg_temp.reject_weight_clear() returns trigger language plpgsql as $$
begin
    if new.weight is null then
        raise exception 'simulated source update failure' using errcode = '23514';
    end if;
    return new;
end;
$$;
create trigger reject_weight_clear before update on pg_temp.daily_logs
for each row execute function pg_temp.reject_weight_clear();

do $$
begin
    -- A failure AFTER saving the destination must roll that save back too.
    begin
        perform pg_temp.move_weight_atomic(
            2,'00000000-0000-0000-0000-000000000001','2026-11-03',72
        );
        raise exception 'Expected source update failure';
    exception when check_violation then null;
    end;
    assert (select weight = 73 from pg_temp.daily_logs where id = 2);
    assert not exists(select 1 from pg_temp.daily_logs where date = '2026-11-03');
end;
$$;

drop trigger reject_weight_clear on pg_temp.daily_logs;
select * from pg_temp.move_weight_atomic(
    2,'00000000-0000-0000-0000-000000000001','2026-11-03',72
);
do $$
begin
    assert (select weight is null and steps = 9000 from pg_temp.daily_logs where id = 2);
    assert (select weight = 72 from pg_temp.daily_logs
            where user_id = '00000000-0000-0000-0000-000000000001' and date = '2026-11-03');
end;
$$;
