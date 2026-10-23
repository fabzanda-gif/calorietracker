alter table public.pantry_items
  add column if not exists quantity_mode text
    not null default 'weight',
  add column if not exists grams_per_portion numeric;

update public.pantry_items
set quantity_mode = 'weight'
where quantity_mode is null;

alter table public.pantry_items
  drop constraint if exists pantry_items_quantity_mode_check;

alter table public.pantry_items
  add constraint pantry_items_quantity_mode_check
  check (quantity_mode in ('weight', 'portion'));

alter table public.pantry_items
  drop constraint if exists pantry_items_grams_per_portion_check;

alter table public.pantry_items
  add constraint pantry_items_grams_per_portion_check
  check (
    grams_per_portion is null
    or grams_per_portion > 0
  );

comment on column public.pantry_items.quantity_mode is
  'weight = quantità a peso/volume; portion = numero di porzioni o pezzi';

comment on column public.pantry_items.grams_per_portion is
  'Peso in grammi di una singola porzione quando quantity_mode = portion';
