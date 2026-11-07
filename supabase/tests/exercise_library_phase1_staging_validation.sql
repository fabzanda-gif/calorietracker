-- SanoSync Phase 1 isolated staging validation.
-- SELECT only: do NOT use this as a substitute for applying migrations
-- to a disposable Supabase branch and exercising RLS with two test users.
-- Expected: 0 rows with passed = false. Run only AFTER Phase 1 migrations.
-- No production schema/data changes in this script.
WITH expected_classification(
  source_id, movement_pattern, training_role, fatigue_cost,
  technical_complexity, stability_requirement
) AS (
 VALUES
  ('0042', 'squat', 'primary', 'high', 'high', 'medium'),
  ('1760', 'squat', 'secondary', 'medium', 'low', 'medium'),
  ('0577', 'horizontal_push', 'secondary', 'medium', 'low', 'low'),
  ('0308', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0974', 'vertical_pull', 'secondary', 'medium', 'low', 'low'),
  ('0990', 'horizontal_pull', 'secondary', 'low', 'low', 'medium'),
  ('0970', 'vertical_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('1429', 'vertical_pull', 'primary', 'high', 'medium', 'medium'),
  ('0178', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0200', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0294', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('2407', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0585', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0586', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0599', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0705', 'core', 'accessory', 'low', 'medium', 'medium'),
  ('0274', 'core', 'accessory', 'low', 'low', 'low'),
  ('0765', 'vertical_push', 'secondary', 'medium', 'medium', 'low'),
  ('0054', 'single_leg', 'secondary', 'high', 'medium', 'high'),
  ('0116', 'hinge', 'primary', 'high', 'high', 'medium'),
  ('0300', 'hinge', 'secondary', 'medium', 'medium', 'medium'),
  ('0336', 'single_leg', 'secondary', 'medium', 'medium', 'high'),
  ('0432', 'hinge', 'secondary', 'medium', 'medium', 'medium'),
  ('drv-hip-raise-bridge', 'hinge', 'accessory', 'low', 'low', 'low'),
  ('new-band-triceps-pushdown', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('2611', 'squat', 'secondary', 'high', 'low', 'low'),
  ('0740', 'squat', 'secondary', 'high', 'low', 'low'),
  ('0743', 'squat', 'primary', 'high', 'medium', 'low'),
  ('0597', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0598', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('3006', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0976', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0980', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0988', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0991', 'hinge', 'secondary', 'medium', 'low', 'medium'),
  ('0582', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0413', 'squat', 'secondary', 'medium', 'low', 'medium'),
  ('0411', 'single_leg', 'secondary', 'high', 'high', 'high'),
  ('0417', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('1379', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0594', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0605', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0999', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0409', 'isolation', 'accessory', 'low', 'medium', 'high'),
  ('0738', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0154', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0326', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0602', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('2137', 'vertical_push', 'secondary', 'medium', 'high', 'medium'),
  ('0361', 'vertical_push', 'secondary', 'medium', 'medium', 'high'),
  ('0192', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0584', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0310', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0031', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0298', 'isolation', 'accessory', 'low', 'low', 'medium'),
  ('0322', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0351', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0194', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0259', 'horizontal_push', 'accessory', 'medium', 'low', 'medium'),
  ('0592', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0061', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0306', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0489', 'hinge', 'accessory', 'low', 'medium', 'medium'),
  ('0983', 'vertical_pull', 'secondary', 'low', 'low', 'medium'),
  ('3144', 'horizontal_pull', 'secondary', 'low', 'low', 'medium'),
  ('0095', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0027', 'horizontal_pull', 'secondary', 'high', 'high', 'medium'),
  ('0570', 'vertical_pull', 'secondary', 'medium', 'low', 'medium'),
  ('2616', 'vertical_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('0861', 'horizontal_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('0213', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('0238', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0248', 'horizontal_pull', 'secondary', 'medium', 'medium', 'low'),
  ('0253', 'vertical_pull', 'primary', 'medium', 'medium', 'medium'),
  ('2987', 'vertical_pull', 'primary', 'medium', 'medium', 'medium'),
  ('0293', 'horizontal_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('1330', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('0327', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('1328', 'horizontal_pull', 'accessory', 'low', 'medium', 'low'),
  ('0406', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0498', 'horizontal_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('drv-kettlebell-deadlift', 'hinge', 'secondary', 'medium', 'medium', 'medium'),
  ('0573', 'hinge', 'accessory', 'low', 'low', 'low'),
  ('0581', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('1349', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('drv-lever-t-bar-row', 'horizontal_pull', 'secondary', 'medium', 'medium', 'low'),
  ('0207', 'vertical_pull', 'secondary', 'medium', 'low', 'low'),
  ('0673', 'vertical_pull', 'secondary', 'medium', 'low', 'low'),
  ('2327', 'vertical_pull', 'primary', 'medium', 'medium', 'medium'),
  ('0218', 'horizontal_pull', 'secondary', 'medium', 'low', 'low'),
  ('0651', 'vertical_pull', 'primary', 'high', 'medium', 'medium'),
  ('0752', 'hinge', 'secondary', 'high', 'medium', 'low'),
  ('0033', 'horizontal_push', 'secondary', 'high', 'medium', 'medium'),
  ('0047', 'horizontal_push', 'primary', 'high', 'medium', 'medium'),
  ('1269', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('drv-chest-dips', 'horizontal_push', 'secondary', 'high', 'medium', 'high'),
  ('0301', 'horizontal_push', 'secondary', 'medium', 'medium', 'medium'),
  ('0302', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('1274', 'horizontal_push', 'secondary', 'medium', 'medium', 'medium'),
  ('0319', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0321', 'horizontal_push', 'secondary', 'medium', 'medium', 'medium'),
  ('0340', 'horizontal_push', 'secondary', 'medium', 'medium', 'medium'),
  ('0620', 'isolation', 'accessory', 'low', 'medium', 'low'),
  ('0493', 'horizontal_push', 'accessory', 'low', 'low', 'low'),
  ('1299', 'horizontal_push', 'secondary', 'medium', 'low', 'low'),
  ('drv-lever-pec-deck-fly', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('drv-push-ups', 'horizontal_push', 'secondary', 'medium', 'low', 'medium'),
  ('0175', 'core', 'accessory', 'low', 'low', 'low'),
  ('0226', 'core', 'accessory', 'low', 'low', 'low'),
  ('1764', 'core', 'secondary', 'medium', 'medium', 'high'),
  ('0474', 'core', 'secondary', 'medium', 'high', 'high'),
  ('0872', 'core', 'accessory', 'low', 'low', 'low'),
  ('0865', 'core', 'accessory', 'low', 'low', 'low'),
  ('1452', 'core', 'accessory', 'low', 'low', 'low'),
  ('0985', 'core', 'accessory', 'low', 'low', 'low'),
  ('drv-chin-ups-pull-ups', 'vertical_pull', 'primary', 'high', 'medium', 'medium'),
  ('drv-ring-high-row', 'horizontal_pull', 'secondary', 'medium', 'medium', 'high'),
  ('0499', 'horizontal_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('0604', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0329', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('1329', 'horizontal_pull', 'secondary', 'medium', 'medium', 'medium'),
  ('3012', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('drv-commando-pull-up', 'vertical_pull', 'secondary', 'high', 'high', 'high'),
  ('drv-cable-bar-lateral-pulldown-wide-shoulder-grip', 'vertical_pull', 'secondary', 'medium', 'low', 'low'),
  ('drv-band-high-fly', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('drv-rotate-push-up-female', 'horizontal_push', 'secondary', 'medium', 'medium', 'high'),
  ('1277', 'isolation', 'accessory', 'low', 'medium', 'high'),
  ('1278', 'isolation', 'accessory', 'low', 'medium', 'high'),
  ('0297', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0333', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('2188', 'isolation', 'accessory', 'low', 'medium', 'medium'),
  ('0190', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0229', 'isolation', 'accessory', 'low', 'low', 'low'),
  ('0374', 'isolation', 'accessory', 'low', 'medium', 'low'),
  ('1451', 'horizontal_push', 'secondary', 'medium', 'low', 'low'),
  ('1005', 'core', 'accessory', 'low', 'low', 'medium'),
  ('0230', 'core', 'accessory', 'low', 'medium', 'medium'),
  ('0862', 'core', 'accessory', 'low', 'medium', 'medium'),
  ('1338', 'core', 'accessory', 'low', 'low', 'medium'),
  ('0325', 'core', 'secondary', 'medium', 'medium', 'medium'),
  ('0981', 'core', 'accessory', 'medium', 'medium', 'medium'),
  ('0600', 'core', 'accessory', 'low', 'medium', 'low'),
  ('0826', 'core', 'secondary', 'medium', 'medium', 'high'),
  ('drv-v-up', 'core', 'secondary', 'medium', 'medium', 'medium'),
  ('drv-sit-ups', 'core', 'accessory', 'low', 'low', 'low')
),
expected_pairs(source_id, target_id, relationship) AS (
 VALUES
  ('0198', '0974', 'close_substitute'),
  ('0208', '0990', 'substitute'),
  ('0334', '0178', 'close_substitute'),
  ('1723', '0200', 'close_substitute'),
  ('0294', '2407', 'close_substitute'),
  ('0586', '0599', 'close_substitute'),
  ('0025', '0577', 'substitute'),
  ('1435', '1760', 'regression'),
  ('1435', '0042', 'substitute'),
  ('1435', '0743', 'substitute'),
  ('1760', '0413', 'close_substitute'),
  ('0417', '0605', 'substitute'),
  ('0585', '0980', 'substitute'),
  ('0289', '0765', 'substitute'),
  ('0294', '0031', 'substitute'),
  ('0334', '0584', 'substitute'),
  ('1723', 'new-band-triceps-pushdown', 'substitute'),
  ('0198', '0207', 'close_substitute'),
  ('0208', '0218', 'close_substitute'),
  ('0293', 'drv-lever-t-bar-row', 'substitute'),
  ('0025', '0047', 'substitute'),
  ('0334', '0192', 'close_substitute'),
  ('0308', 'drv-lever-pec-deck-fly', 'substitute'),
  ('drv-push-ups', '0493', 'regression'),
  ('0253', '0970', 'regression'),
  ('0095', '0406', 'close_substitute'),
  ('0175', '1452', 'substitute'),
  ('drv-chin-ups-pull-ups', '0970', 'regression'),
  ('0406', '0604', 'substitute'),
  ('0297', '0592', 'substitute'),
  ('drv-push-ups', 'drv-rotate-push-up-female', 'progression'),
  ('0175', '1005', 'substitute'),
  ('drv-cable-bar-lateral-pulldown-wide-shoulder-grip', '0198', 'close_substitute')
),
expected_edges AS (
 SELECT source_id, target_id, relationship FROM expected_pairs
 UNION ALL
 SELECT target_id, source_id, relationship FROM expected_pairs
 WHERE relationship IN ('close_substitute','substitute')
),
classified AS (
 SELECT ec.*, e.id, e.active, e.approved_for_generation,
        e.movement_pattern AS actual_movement_pattern,
        e.training_role AS actual_training_role,
        e.fatigue_cost AS actual_fatigue_cost,
        e.technical_complexity AS actual_complexity,
        e.stability_requirement AS actual_stability
 FROM expected_classification ec
 LEFT JOIN public.exercises e
   ON e.source='free-exercise-db-with-videos'
  AND e.source_id=ec.source_id
),
joined_relations AS (
 SELECT ee.source_id,ee.target_id,ee.relationship,
        er.source_exercise_id IS NOT NULL AS found
 FROM expected_edges ee
 LEFT JOIN public.exercises src
   ON src.source='free-exercise-db-with-videos' AND src.source_id=ee.source_id
 LEFT JOIN public.exercises dst
   ON dst.source='free-exercise-db-with-videos' AND dst.source_id=ee.target_id
 LEFT JOIN public.exercise_relationships er
   ON er.source_exercise_id=src.id AND er.target_exercise_id=dst.id
  AND er.relationship=ee.relationship
),
checks(name,passed,details) AS (
 SELECT 'curated_145_all_present',
        (SELECT count(*)=145 AND count(id)=145 FROM classified),
        (SELECT count(*)::text||'/145 source IDs' FROM classified WHERE id IS NOT NULL)
 UNION ALL
 SELECT 'curated_145_metadata_matches',
        NOT EXISTS (
          SELECT 1 FROM classified WHERE id IS NULL
           OR actual_movement_pattern IS DISTINCT FROM movement_pattern
           OR actual_training_role IS DISTINCT FROM training_role
           OR actual_fatigue_cost IS DISTINCT FROM fatigue_cost
           OR actual_complexity IS DISTINCT FROM technical_complexity
           OR actual_stability IS DISTINCT FROM stability_requirement
        ),
        'Compare exact 6-column values per curated source_id'
 UNION ALL
 SELECT 'not_automatically_approved',
        NOT EXISTS (SELECT 1 FROM classified WHERE approved_for_generation),
        'Batch metadata must not approve exercises for generation'
 UNION ALL
 SELECT 'relationships_all_61_edges_present',
        (SELECT count(*)=61 AND count(*) FILTER (WHERE found)=61 FROM joined_relations),
        (SELECT count(*) FILTER (WHERE found)::text||'/61 edges' FROM joined_relations)
 UNION ALL
 SELECT 'no_invalid_relationship_scores',
        NOT EXISTS (
          SELECT 1 FROM public.exercise_relationships
          WHERE source_exercise_id=target_exercise_id
            OR similarity_score < 0 OR similarity_score > 1
        ),
        'No self relationships or out-of-range similarity'
 UNION ALL
 SELECT 'exercise_library_authenticated_read_only',
        has_table_privilege('authenticated','public.exercises','SELECT')
        AND NOT has_table_privilege('authenticated','public.exercises','UPDATE')
        AND NOT has_table_privilege('authenticated','public.exercises','INSERT'),
        'Catalog is readable but not writable by authenticated users'
 UNION ALL
 SELECT 'exercise_library_anon_denied',
        NOT has_table_privilege('anon','public.exercises','SELECT')
        AND NOT has_table_privilege('anon','public.exercise_relationships','SELECT'),
        'Anonymous role cannot read library'
 UNION ALL
 SELECT 'preferences_rls_enabled',
        EXISTS (
          SELECT 1 FROM pg_class WHERE oid='public.training_exercise_preferences'::regclass
           AND relrowsecurity
        ),
        'Owner-scoped preference table RLS must be enabled'
 UNION ALL
 SELECT 'preferences_four_owner_policies',
        (SELECT count(*)=4 FROM pg_policies
         WHERE schemaname='public' AND tablename='training_exercise_preferences'
           AND (qual LIKE '%auth.uid()%' OR with_check LIKE '%auth.uid()%')),
        'SELECT, INSERT, UPDATE, DELETE must scope rows by auth.uid()'
 UNION ALL
 SELECT 'preferences_anon_denied',
        NOT has_table_privilege('anon','public.training_exercise_preferences','SELECT')
        AND NOT has_table_privilege('anon','public.training_exercise_preferences','INSERT'),
        'Anonymous role cannot access preferences'
 UNION ALL
 SELECT 'preferences_auth_permissions',
        has_table_privilege('authenticated','public.training_exercise_preferences','SELECT')
        AND has_table_privilege('authenticated','public.training_exercise_preferences','INSERT')
        AND has_table_privilege('authenticated','public.training_exercise_preferences','UPDATE')
        AND has_table_privilege('authenticated','public.training_exercise_preferences','DELETE'),
        'Authenticated DML allowed subject to RLS'
)
SELECT * FROM checks ORDER BY name;
