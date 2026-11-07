alter table public.ingredients
  add column if not exists kind text not null default 'ingredient',
  add column if not exists meal_slots text[] not null default '{}';

alter table public.ingredients
  drop constraint if exists ingredients_kind_check;

alter table public.ingredients
  add constraint ingredients_kind_check
  check (
    kind in ('ingredient', 'product', 'prepared_food')
  );

alter table public.ingredients
  drop constraint if exists ingredients_meal_slots_check;

alter table public.ingredients
  add constraint ingredients_meal_slots_check
  check (
    meal_slots <@ array[
      'breakfast',
      'lunch',
      'snack',
      'dinner'
    ]::text[]
  );
