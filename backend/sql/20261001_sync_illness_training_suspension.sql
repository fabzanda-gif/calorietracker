create or replace function public.sync_special_period_training_suspension()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  if tg_op = 'DELETE' then
    update public.planned_activities
    set status = 'planned',
        suspended_by_special_period_id = null,
        updated_at = now()
    where suspended_by_special_period_id = old.id
      and status = 'suspended';
    return old;
  end if;

  if tg_op = 'UPDATE' then
    update public.planned_activities
    set status = 'planned',
        suspended_by_special_period_id = null,
        updated_at = now()
    where suspended_by_special_period_id = new.id
      and status = 'suspended';
  end if;

  if new.training_policy = 'suspend' then
    update public.planned_activities
    set status = 'suspended',
        suspended_by_special_period_id = new.id,
        updated_at = now()
    where user_id = new.user_id
      and scheduled_date between new.start_date and new.end_date
      and status = 'planned';
  end if;

  return new;
end;
$$;

drop trigger if exists special_period_training_suspension on public.special_periods;
drop trigger if exists special_period_training_restore_before_delete on public.special_periods;

create trigger special_period_training_suspension
after insert or update on public.special_periods
for each row execute function public.sync_special_period_training_suspension();

create trigger special_period_training_restore_before_delete
before delete on public.special_periods
for each row execute function public.sync_special_period_training_suspension();

create or replace function public.apply_special_period_to_planned_activity()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  illness_id uuid;
begin
  if new.status = 'planned' then
    select sp.id
      into illness_id
    from public.special_periods sp
    where sp.user_id = new.user_id
      and sp.training_policy = 'suspend'
      and new.scheduled_date between sp.start_date and sp.end_date
    order by case when sp.period_type = 'illness' then 0 else 1 end,
             sp.start_date desc
    limit 1;

    if illness_id is not null then
      new.status := 'suspended';
      new.suspended_by_special_period_id := illness_id;
    else
      new.suspended_by_special_period_id := null;
    end if;
  elsif new.status = 'suspended' and new.suspended_by_special_period_id is not null then
    if not exists (
      select 1
      from public.special_periods sp
      where sp.id = new.suspended_by_special_period_id
        and sp.user_id = new.user_id
        and sp.training_policy = 'suspend'
        and new.scheduled_date between sp.start_date and sp.end_date
    ) then
      new.status := 'planned';
      new.suspended_by_special_period_id := null;
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists planned_activity_special_period_guard on public.planned_activities;
create trigger planned_activity_special_period_guard
before insert or update of scheduled_date, status on public.planned_activities
for each row execute function public.apply_special_period_to_planned_activity();
