-- Rimuove attività automatiche prive di passi netti.
-- Non modifica attività manuali, GPX o stime positive.

delete from public.activities
where activity_name = 'Passi (Stima)'
  and coalesce(burned_calories, 0) <= 0;
