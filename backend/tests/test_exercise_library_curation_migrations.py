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
        / "20261107211000_curate_exercise_library_phase1_batch2.sql"
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
    assert len(exercise_ids) == 43
    assert len(set(exercise_ids)) == 43

    relations = sql.split("with reviewed_pairs(", 1)[1].split(
        "),\nresolved as", 1
    )[0]
    pairs = re.findall(
        r"^\s*\('([^']+)','([^']+)','substitute',null,",
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
