"""Guard curated Exercise Library migrations against accidental broad approvals.

The test deliberately reads only versioned SQL; it does not require a
Supabase connection and does not assert deployment has occurred.
"""
from pathlib import Path
import re


MIGRATIONS = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def test_phase1_second_curation_batch_is_bounded_and_non_approving():
    sql = (
        MIGRATIONS
        / "20261107233923_curate_exercise_library_phase1_batch2.sql"
    ).read_text(encoding="utf-8")

    # Match source IDs only in the curated VALUES block, not relationships.
    curated = sql.split("with curated(", 1)[1].split(
        "update public.exercises", 1
    )[0]
    exercise_ids = re.findall(
        r"^\s*\('([^']+)','(?:squat|hinge|single_leg|"
        r"horizontal_push|vertical_push|isolation)'",
        curated,
        re.MULTILINE,
    )
    assert len(exercise_ids) == 44
    assert len(set(exercise_ids)) == 44

    relations = sql.split("with reviewed_pairs(", 1)[1].split(
        "),\nresolved as", 1
    )[0]
    pairs = re.findall(
        r"^\s*\('([^']+)','([^']+)','(?:close_substitute|substitute)',null,",
        relations,
        re.MULTILINE,
    )
    assert len(pairs) == 9
    assert len(set(pairs)) == 9
    assert all(source != target for source, target in pairs)

    assert "approved_for_generation = false" in sql
    assert not re.search(
        r"set\s+approved_for_generation\s*=\s*true",
        sql,
        flags=re.IGNORECASE,
    )
    assert not re.search(
        r"delete\s+from\s+public\.exercises",
        sql,
        flags=re.IGNORECASE,
    )


def test_phase1_third_batch_is_bounded_and_does_not_approve():
    sql = (
        MIGRATIONS
        / "20261107233939_curate_exercise_library_phase1_batch3.sql"
    ).read_text(encoding="utf-8")
    curated = sql.split("with curated (", 1)[1].split(
        "update public.exercises", 1
    )[0]
    ids = re.findall(
        r"^\s*\('([^']+)','(?:squat|hinge|horizontal_pull|vertical_pull|"
        r"horizontal_push|isolation|core)'",
        curated,
        re.MULTILINE,
    )
    assert len(ids) == 53
    assert len(set(ids)) == 53

    relationships = sql.split("with reviewed_pairs (", 1)[1].split(
        "),\nresolved as", 1
    )[0]
    pairs = re.findall(
        r"^\s*\('([^']+)','([^']+)','(?:close_substitute|substitute|regression)'",
        relationships,
        re.MULTILINE,
    )
    assert len(pairs) == 10
    assert len(set(pairs)) == 10
    assert all(source != target for source, target in pairs)
    assert "approved_for_generation = false" in sql
    assert not re.search(
        r"set\s+approved_for_generation\s*=\s*true",
        sql,
        flags=re.IGNORECASE,
    )


def test_phase1_curation_batches_cover_155_unique_exercises_without_approval():
    files = (
        ("20261107233829_curate_exercise_library_phase1_batch1.sql", 18),
        ("20261107233923_curate_exercise_library_phase1_batch2.sql", 44),
        ("20261107233939_curate_exercise_library_phase1_batch3.sql", 53),
        ("20261107233949_curate_exercise_library_phase1_batch4.sql", 30),
    )
    all_ids = []
    for filename, expected_count in files:
        sql = (MIGRATIONS / filename).read_text(encoding="utf-8")
        # Take only exercise-metadata VALUES; the later VALUES belong to
        # relationships and must not be confused with curated entries.
        first_update = sql.index("update public.exercises")
        batch = sql[:first_update]
        ids = re.findall(
            r"^\s*\('([^']+)','(?:squat|hinge|single_leg|"
            r"horizontal_push|vertical_push|horizontal_pull|vertical_pull|"
            r"core|isolation)'",
            batch,
            re.MULTILINE,
        )
        assert len(ids) == expected_count, filename
        assert len(set(ids)) == expected_count, filename
        assert "approved_for_generation=false" in sql.replace(" ", "")
        assert not re.search(
            r"set\s+approved_for_generation\s*=\s*true",
            sql,
            flags=re.IGNORECASE,
        )
        all_ids.extend(ids)

    golden = (
        "1435", "0025", "0334", "0464", "0553",
        "0198", "0314", "0208", "1723", "0289"
    )
    assert len(all_ids) == 145
    assert len(set(all_ids)) == 145
    assert not set(all_ids).intersection(golden)
    assert len(set(all_ids).union(golden)) == 155
