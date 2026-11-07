"""Offline preflight: ensure staging SQL assertions track curated migrations.

This validates the audit artifact against the versioned data rather than
claiming an isolated PostgreSQL execution happened in GitHub Actions.
"""
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS = ROOT / "supabase" / "migrations"
PREFLIGHT = ROOT / "supabase" / "tests" / "exercise_library_phase1_staging_validation.sql"
BATCHES = [
    "20261107210000_curate_exercise_library_phase1_batch1.sql",
    "20261107211000_curate_exercise_library_phase1_batch2.sql",
    "20261107212000_curate_exercise_library_phase1_batch3.sql",
    "20261107213000_curate_exercise_library_phase1_batch4.sql",
]
MOVEMENTS = {
    "squat", "hinge", "horizontal_push", "vertical_push",
    "horizontal_pull", "vertical_pull", "single_leg", "core",
    "isolation", "carry", "cardio",
}
ROLES = {"primary", "secondary", "accessory"}
LEVELS = {"low", "medium", "high"}
RELATIONSHIPS = {
    "close_substitute", "substitute", "regression", "progression",
    "similar",
}

CLASSIFICATION = re.compile(
    r"\('([^']+)'\s*,\s*'(squat|hinge|horizontal_push|"
    r"vertical_push|horizontal_pull|vertical_pull|single_leg|"
    r"core|isolation|carry|cardio)'\s*,\s*"
    r"'(primary|secondary|accessory)'\s*,\s*"
    r"'(low|medium|high)'\s*,\s*"
    r"'(low|medium|high)'\s*,\s*"
    r"'(low|medium|high)'\)"
)
RELATIONSHIP = re.compile(
    r"\('([^']+)'\s*,\s*'([^']+)'\s*,\s*"
    r"'(close_substitute|substitute|regression|progression|similar)'"
)


def _reviewed_data():
    classifications = []
    relationships = []
    for name in BATCHES:
        sql = (MIGRATIONS / name).read_text(encoding="utf-8")
        update_pos = sql.index("update public.exercises")
        classifications.extend(CLASSIFICATION.findall(sql[:update_pos]))
        pair_start = (
            sql.find("with reviewed_pairs")
            if "with reviewed_pairs" in sql else sql.index("with pairs(")
        )
        relationships.extend(RELATIONSHIP.findall(sql[pair_start:]))
        assert "approved_for_generation" in sql
        assert not re.search(
            r"set\s+approved_for_generation\s*=\s*true",
            sql, flags=re.IGNORECASE,
        )
    return classifications, relationships


def test_staging_preflight_matches_every_curated_value_and_pair():
    curated, reviewed = _reviewed_data()
    assert len(curated) == len(set(curated)) == 145
    assert len({record[0] for record in curated}) == 145
    assert len(reviewed) == len(set(reviewed)) == 33
    assert all(row[1] in MOVEMENTS and row[2] in ROLES for row in curated)
    assert all(set(row[3:]) <= LEVELS for row in curated)
    assert all(left != right and kind in RELATIONSHIPS
               for left, right, kind in reviewed)
    assert len(set(reviewed)) == 33

    # Every substitute endpoint must have a known movement classification.
    # Otherwise the alternative API could offer an unclassified exercise,
    # as happened with the band triceps pushdown during this audit.
    golden_patterns = {
        "1435": "squat",
        "0025": "horizontal_push",
        "0334": "isolation",
        "0464": "core",
        "0553": "vertical_push",
        "0198": "vertical_pull",
        "0314": "horizontal_push",
        "0208": "horizontal_pull",
        "1723": "isolation",
        "0289": "vertical_push",
    }
    patterns = {row[0]: row[1] for row in curated}
    patterns.update(golden_patterns)
    for source, target, _relationship in reviewed:
        assert source in patterns, source
        assert target in patterns, target
        assert patterns[source] == patterns[target], (source, target)

    query = PREFLIGHT.read_text(encoding="utf-8")
    classified_section = query.split("expected_classification(", 1)[1].split(
        "expected_pairs(", 1
    )[0]
    pair_section = query.split("expected_pairs(", 1)[1].split(
        "expected_edges AS", 1
    )[0]
    assert set(CLASSIFICATION.findall(classified_section)) == set(curated)
    assert set(RELATIONSHIP.findall(pair_section)) == set(reviewed)
    assert len(CLASSIFICATION.findall(classified_section)) == 145
    assert len(RELATIONSHIP.findall(pair_section)) == 33
    assert "count(*)=61" in query
    assert "preferences_rls_enabled" in query
    assert "preferences_four_owner_policies" in query
    assert "exercise_library_anon_denied" in query


def test_preference_policy_has_owner_check_for_each_operation():
    sql = (MIGRATIONS /
        "20261107214000_add_training_exercise_preferences.sql"
    ).read_text(encoding="utf-8").lower()
    assert "enable row level security" in sql
    assert "references auth.users(id)" in sql
    assert "references public.exercises(id)" in sql
    for operation in ("select", "insert", "update", "delete"):
        block = sql.split(
            f"on public.training_exercise_preferences for {operation}",
            1
        )[1].split(";", 1)[0]
        assert "to authenticated" in block
        assert "auth.uid()" in block
        if operation == "update":
            assert "using" in block
            assert "with check" in block
    assert "grant select, insert, update, delete" in sql


def test_relationship_schema_allows_null_score_but_not_invalid_edges():
    schema = (MIGRATIONS /
        "20261107191500_add_exercise_library_v1.sql"
    ).read_text(encoding="utf-8")
    assert "similarity_score numeric null" in schema
    assert "similarity_score between 0 and 1" in schema
    assert "source_exercise_id <> target_exercise_id" in schema
    assert "on delete cascade" in schema.lower()
    assert "primary key (" in schema
