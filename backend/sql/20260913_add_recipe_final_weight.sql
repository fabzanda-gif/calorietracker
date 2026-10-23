alter table public.recipe_library
    add column if not exists final_weight_g numeric;

alter table public.recipe_library
    drop constraint if exists recipe_library_final_weight_g_check,
    add constraint recipe_library_final_weight_g_check
        check (
            final_weight_g is null
            or final_weight_g > 0
        );
