create table if not exists public.exercise_families (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    name_default text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.exercises (
    id uuid primary key default gen_random_uuid(),
    slug text not null unique,
    family_id uuid null
        references public.exercise_families(id)
        on delete set null,
    source text not null,
    source_id text not null,
    source_license text not null,
    name_default text not null,
    body_part text null,
    target_muscle text null,
    movement_pattern text null
        check (
            movement_pattern is null
            or movement_pattern in (
                'squat',
                'hinge',
                'horizontal_push',
                'vertical_push',
                'horizontal_pull',
                'vertical_pull',
                'single_leg',
                'core',
                'isolation',
                'carry',
                'cardio'
            )
        ),
    mechanic text null
        check (
            mechanic is null
            or mechanic in ('compound', 'isolation')
        ),
    laterality text not null default 'bilateral'
        check (
            laterality in (
                'bilateral',
                'unilateral',
                'alternating'
            )
        ),
    difficulty text null
        check (
            difficulty is null
            or difficulty in (
                'beginner',
                'intermediate',
                'advanced'
            )
        ),
    training_role text null
        check (
            training_role is null
            or training_role in (
                'primary',
                'secondary',
                'accessory'
            )
        ),
    fatigue_cost text null
        check (
            fatigue_cost is null
            or fatigue_cost in (
                'low',
                'medium',
                'high'
            )
        ),
    technical_complexity text null
        check (
            technical_complexity is null
            or technical_complexity in (
                'low',
                'medium',
                'high'
            )
        ),
    stability_requirement text null
        check (
            stability_requirement is null
            or stability_requirement in (
                'low',
                'medium',
                'high'
            )
        ),
    tracking_type text not null default 'reps_load'
        check (
            tracking_type in (
                'reps_load',
                'reps_bodyweight',
                'duration',
                'distance'
            )
        ),
    load_convention text not null default 'reported'
        check (
            load_convention in (
                'reported',
                'total',
                'per_hand',
                'bodyweight',
                'bodyweight_plus_external',
                'assistance'
            )
        ),
    strength_score smallint null
        check (
            strength_score is null
            or strength_score between 1 and 5
        ),
    hypertrophy_score smallint null
        check (
            hypertrophy_score is null
            or hypertrophy_score between 1 and 5
        ),
    general_fitness_score smallint null
        check (
            general_fitness_score is null
            or general_fitness_score between 1 and 5
        ),
    approved_for_generation boolean not null default false,
    active boolean not null default true,
    catalog_version integer not null default 1
        check (catalog_version >= 1),
    replaced_by uuid null
        references public.exercises(id)
        on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint exercises_source_id_unique
        unique (source, source_id)
);

create index if not exists exercises_active_name_idx
    on public.exercises(active, name_default);
create index if not exists exercises_generation_idx
    on public.exercises(approved_for_generation, active);
create index if not exists exercises_body_part_idx
    on public.exercises(body_part);
create index if not exists exercises_target_muscle_idx
    on public.exercises(target_muscle);

create table if not exists public.exercise_translations (
    exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    language text not null,
    name text not null,
    short_description text null,
    instructions text null,
    steps jsonb not null default '[]'::jsonb,
    form_cues jsonb not null default '[]'::jsonb,
    common_mistakes jsonb not null default '[]'::jsonb,
    breathing text null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (exercise_id, language),
    constraint exercise_translation_language_check
        check (language ~ '^[a-z]{2}(-[A-Z]{2})?$'),
    constraint exercise_translation_steps_array
        check (jsonb_typeof(steps) = 'array'),
    constraint exercise_translation_cues_array
        check (jsonb_typeof(form_cues) = 'array'),
    constraint exercise_translation_mistakes_array
        check (jsonb_typeof(common_mistakes) = 'array')
);

create table if not exists public.exercise_aliases (
    exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    language text not null default 'en',
    alias text not null,
    created_at timestamptz not null default now(),
    primary key (exercise_id, language, alias)
);

create index if not exists exercise_aliases_alias_idx
    on public.exercise_aliases(lower(alias));

create table if not exists public.muscles (
    id uuid primary key default gen_random_uuid(),
    key text not null unique,
    name_default text not null,
    parent_id uuid null
        references public.muscles(id)
        on delete set null,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.exercise_muscles (
    exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    muscle_id uuid not null
        references public.muscles(id)
        on delete restrict,
    role text not null
        check (role in ('primary', 'secondary')),
    contribution numeric not null
        check (contribution > 0 and contribution <= 1),
    primary key (exercise_id, muscle_id, role)
);

create index if not exists exercise_muscles_muscle_idx
    on public.exercise_muscles(muscle_id, role);

create table if not exists public.equipment (
    id uuid primary key default gen_random_uuid(),
    key text not null unique,
    name_default text not null,
    active boolean not null default true,
    created_at timestamptz not null default now()
);

create table if not exists public.exercise_equipment (
    exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    equipment_id uuid not null
        references public.equipment(id)
        on delete restrict,
    role text not null default 'primary'
        check (role in ('primary', 'required')),
    primary key (exercise_id, equipment_id, role)
);

create index if not exists exercise_equipment_equipment_idx
    on public.exercise_equipment(equipment_id);

create table if not exists public.exercise_relationships (
    source_exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    target_exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    relationship text not null
        check (
            relationship in (
                'close_substitute',
                'substitute',
                'regression',
                'progression',
                'similar'
            )
        ),
    similarity_score numeric null
        check (
            similarity_score is null
            or similarity_score between 0 and 1
        ),
    rationale text null,
    created_at timestamptz not null default now(),
    primary key (
        source_exercise_id,
        target_exercise_id,
        relationship
    ),
    constraint exercise_relationships_not_self
        check (source_exercise_id <> target_exercise_id)
);

create table if not exists public.exercise_media (
    id uuid primary key default gen_random_uuid(),
    exercise_id uuid not null
        references public.exercises(id)
        on delete cascade,
    media_type text not null
        check (
            media_type in (
                'video',
                'thumbnail',
                'image'
            )
        ),
    variant text not null default 'neutral'
        check (
            variant in (
                'male',
                'female',
                'neutral'
            )
        ),
    url text not null,
    source text not null,
    source_url text null,
    source_license text null,
    attribution text null,
    is_primary boolean not null default false,
    created_at timestamptz not null default now(),
    constraint exercise_media_unique
        unique (
            exercise_id,
            media_type,
            variant,
            url
        )
);

create index if not exists exercise_media_exercise_idx
    on public.exercise_media(exercise_id, media_type);

alter table public.strength_workout_exercises
    add column if not exists exercise_id uuid null
        references public.exercises(id)
        on delete set null;

create index if not exists
    strength_workout_exercises_library_idx
on public.strength_workout_exercises(exercise_id);

alter table public.exercise_families enable row level security;
alter table public.exercises enable row level security;
alter table public.exercise_translations enable row level security;
alter table public.exercise_aliases enable row level security;
alter table public.muscles enable row level security;
alter table public.exercise_muscles enable row level security;
alter table public.equipment enable row level security;
alter table public.exercise_equipment enable row level security;
alter table public.exercise_relationships enable row level security;
alter table public.exercise_media enable row level security;

revoke all on table public.exercise_families from anon, authenticated;
revoke all on table public.exercises from anon, authenticated;
revoke all on table public.exercise_translations from anon, authenticated;
revoke all on table public.exercise_aliases from anon, authenticated;
revoke all on table public.muscles from anon, authenticated;
revoke all on table public.exercise_muscles from anon, authenticated;
revoke all on table public.equipment from anon, authenticated;
revoke all on table public.exercise_equipment from anon, authenticated;
revoke all on table public.exercise_relationships from anon, authenticated;
revoke all on table public.exercise_media from anon, authenticated;

grant select on table public.exercise_families to authenticated;
grant select on table public.exercises to authenticated;
grant select on table public.exercise_translations to authenticated;
grant select on table public.exercise_aliases to authenticated;
grant select on table public.muscles to authenticated;
grant select on table public.exercise_muscles to authenticated;
grant select on table public.equipment to authenticated;
grant select on table public.exercise_equipment to authenticated;
grant select on table public.exercise_relationships to authenticated;
grant select on table public.exercise_media to authenticated;

grant all on table public.exercise_families to service_role;
grant all on table public.exercises to service_role;
grant all on table public.exercise_translations to service_role;
grant all on table public.exercise_aliases to service_role;
grant all on table public.muscles to service_role;
grant all on table public.exercise_muscles to service_role;
grant all on table public.equipment to service_role;
grant all on table public.exercise_equipment to service_role;
grant all on table public.exercise_relationships to service_role;
grant all on table public.exercise_media to service_role;

drop policy if exists "exercise_families_read_authenticated"
    on public.exercise_families;
create policy "exercise_families_read_authenticated"
    on public.exercise_families
    for select
    to authenticated
    using (true);

drop policy if exists "exercises_read_authenticated"
    on public.exercises;
create policy "exercises_read_authenticated"
    on public.exercises
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_translations_read_authenticated"
    on public.exercise_translations;
create policy "exercise_translations_read_authenticated"
    on public.exercise_translations
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_aliases_read_authenticated"
    on public.exercise_aliases;
create policy "exercise_aliases_read_authenticated"
    on public.exercise_aliases
    for select
    to authenticated
    using (true);

drop policy if exists "muscles_read_authenticated"
    on public.muscles;
create policy "muscles_read_authenticated"
    on public.muscles
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_muscles_read_authenticated"
    on public.exercise_muscles;
create policy "exercise_muscles_read_authenticated"
    on public.exercise_muscles
    for select
    to authenticated
    using (true);

drop policy if exists "equipment_read_authenticated"
    on public.equipment;
create policy "equipment_read_authenticated"
    on public.equipment
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_equipment_read_authenticated"
    on public.exercise_equipment;
create policy "exercise_equipment_read_authenticated"
    on public.exercise_equipment
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_relationships_read_authenticated"
    on public.exercise_relationships;
create policy "exercise_relationships_read_authenticated"
    on public.exercise_relationships
    for select
    to authenticated
    using (true);

drop policy if exists "exercise_media_read_authenticated"
    on public.exercise_media;
create policy "exercise_media_read_authenticated"
    on public.exercise_media
    for select
    to authenticated
    using (true);
