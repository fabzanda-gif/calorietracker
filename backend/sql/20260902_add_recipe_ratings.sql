alter table public.recipe_library
    add column if not exists taste_rating smallint,
    add column if not exists ease_rating smallint;

alter table public.recipe_library
    drop constraint if exists recipe_library_taste_rating_check,
    add constraint recipe_library_taste_rating_check
        check (taste_rating is null or taste_rating between 1 and 5),
    drop constraint if exists recipe_library_ease_rating_check,
    add constraint recipe_library_ease_rating_check
        check (ease_rating is null or ease_rating between 1 and 5);
