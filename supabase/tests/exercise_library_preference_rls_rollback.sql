-- Transactional RLS isolation test for a disposable Supabase branch ONLY.
-- Prerequisite: Exercise Library + training_exercise_preferences migrations.
-- Run using a branch-level privileged SQL editor/psql connection.
-- This script creates 2 temporary auth users and preferences, then ROLLBACKs.
-- NEVER run on production. Do not change the two reserved test IDs.
BEGIN;

INSERT INTO auth.users (id, email, aud, role)
VALUES
 ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa','sanosync-rls-a@example.invalid','authenticated','authenticated'),
 ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb','sanosync-rls-b@example.invalid','authenticated','authenticated');

-- User A: can insert own preference.
SET LOCAL ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
DO $$
BEGIN
  IF auth.uid() IS DISTINCT FROM 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid THEN
    RAISE EXCEPTION 'RLS test JWT A not configured';
  END IF;
END $$;

INSERT INTO public.training_exercise_preferences (user_id,exercise_id,preference)
SELECT 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid, id, 'preferred'
FROM public.exercises
WHERE source='free-exercise-db-with-videos' AND source_id='1435';

DO $$
BEGIN
  IF (SELECT count(*) FROM public.training_exercise_preferences) <> 1 THEN
    RAISE EXCEPTION 'Owner A cannot see their own preference';
  END IF;
END $$;

-- User B: MUST NOT read, modify or delete A's preference.
SELECT set_config('request.jwt.claim.sub', 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', true);
DO $$
DECLARE affected integer;
DECLARE was_blocked boolean := false;
BEGIN
  IF auth.uid() IS DISTINCT FROM 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid THEN
    RAISE EXCEPTION 'RLS test JWT B not configured';
  END IF;
  IF (SELECT count(*) FROM public.training_exercise_preferences) <> 0 THEN
    RAISE EXCEPTION 'Cross-user SELECT leakage';
  END IF;
  UPDATE public.training_exercise_preferences
     SET preference='excluded'
   WHERE user_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid;
  GET DIAGNOSTICS affected = ROW_COUNT;
  IF affected <> 0 THEN
    RAISE EXCEPTION 'Cross-user UPDATE leakage';
  END IF;
  DELETE FROM public.training_exercise_preferences
   WHERE user_id='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid;
  GET DIAGNOSTICS affected = ROW_COUNT;
  IF affected <> 0 THEN
    RAISE EXCEPTION 'Cross-user DELETE leakage';
  END IF;
  BEGIN
    INSERT INTO public.training_exercise_preferences (user_id,exercise_id,preference)
    SELECT 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid, id, 'excluded'
    FROM public.exercises
    WHERE source='free-exercise-db-with-videos' AND source_id='0025';
  EXCEPTION
    WHEN insufficient_privilege THEN
      was_blocked := true;
  END;
  IF NOT was_blocked THEN
    RAISE EXCEPTION 'Cross-user INSERT not blocked by RLS';
  END IF;
END $$;

-- User B can manage B's own preference, and A still cannot see B's.
INSERT INTO public.training_exercise_preferences (user_id,exercise_id,preference)
SELECT 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'::uuid, id, 'excluded'
FROM public.exercises
WHERE source='free-exercise-db-with-videos' AND source_id='1435';

DO $$
BEGIN
  IF (SELECT count(*) FROM public.training_exercise_preferences) <> 1 THEN
    RAISE EXCEPTION 'Owner B cannot see precisely one own preference';
  END IF;
END $$;

SELECT set_config('request.jwt.claim.sub', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', true);
DO $$
BEGIN
  IF (SELECT count(*) FROM public.training_exercise_preferences) <> 1 THEN
    RAISE EXCEPTION 'User A sees another account preference';
  END IF;
END $$;

-- All test rows (including test auth.users) are discarded.
ROLLBACK;
