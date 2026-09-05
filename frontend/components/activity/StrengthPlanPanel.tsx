"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";

import { StrengthProgramOverview } from "@/components/activity/StrengthProgramOverview";

import {
  applyStrengthProgression,
  createStrengthPlan,
  getStrengthPlanDetail,
  getStrengthPlans,
  getStrengthProgressionPreview,
  getStrengthWorkoutOutcome,
  logStrengthWorkout,
  previewStrengthPlan,
  type StrengthExperience,
  type StrengthGoal,
  type StrengthPlanDetailResponse,
  type StrengthPlanPreviewResponse,
  type StrengthProgressionPreviewResponse,
  type StrengthWorkout,
  type StrengthWorkoutOutcome,
} from "@/lib/api/strength";

import styles from "./StrengthPlanPanel.module.css";


interface SetDraft {
  reps: string;
  loadKg: string;
  rir: string;
}


function todayIso(): string {
  const now = new Date();

  const year = now.getFullYear();
  const month = String(
    now.getMonth() + 1,
  ).padStart(2, "0");
  const day = String(
    now.getDate(),
  ).padStart(2, "0");

  return `${year}-${month}-${day}`;
}


function formatDate(value: string): string {
  return new Date(
    `${value}T00:00:00`,
  ).toLocaleDateString(
    "it-IT",
    {
      weekday: "short",
      day: "numeric",
      month: "short",
    },
  );
}


function goalLabel(
  value: StrengthGoal,
): string {
  const labels: Record<
    StrengthGoal,
    string
  > = {
    hypertrophy: "Ipertrofia",
    strength: "Forza",
    general_fitness: "Fitness generale",
  };

  return labels[value];
}


function experienceLabel(
  value: StrengthExperience,
): string {
  const labels: Record<
    StrengthExperience,
    string
  > = {
    beginner: "Principiante",
    intermediate: "Intermedio",
    advanced: "Avanzato",
  };

  return labels[value];
}


function outcomeLabel(
  value: string,
): string {
  if (value === "over_target") {
    return "Sopra target";
  }

  if (value === "under_target") {
    return "Sotto target";
  }

  return "In target";
}


function actionLabel(
  value: string,
): string {
  if (value === "increase_load") {
    return "Aumenta carico";
  }

  if (value === "reduce_load") {
    return "Riduci carico";
  }

  return "Mantieni carico";
}


function initialDrafts(
  workout: StrengthWorkout,
): Record<string, SetDraft[]> {
  const result:
    Record<string, SetDraft[]> = {};

  for (const exercise of workout.exercises) {
    result[exercise.id] = Array.from(
      {
        length: exercise.target_sets,
      },
      () => ({
        reps: String(
          exercise.target_reps_min,
        ),
        loadKg:
          exercise.prescribed_load_kg != null
            ? String(
                exercise.prescribed_load_kg,
              )
            : "",
        rir:
          exercise.target_rir != null
            ? String(exercise.target_rir)
            : "",
      }),
    );
  }

  return result;
}


export function StrengthPlanPanel() {
  const { accessToken } = useAuth();

  const [
    detail,
    setDetail,
  ] = useState<
    StrengthPlanDetailResponse | null
  >(null);

  const [
    loading,
    setLoading,
  ] = useState(false);

  const [
    error,
    setError,
  ] = useState<string | null>(null);

  const [
    message,
    setMessage,
  ] = useState<string | null>(null);

  const [
    goal,
    setGoal,
  ] = useState<StrengthGoal>(
    "hypertrophy",
  );

  const [
    experience,
    setExperience,
  ] = useState<StrengthExperience>(
    "intermediate",
  );

  const [
    sessions,
    setSessions,
  ] = useState<2 | 3 | 4>(3);

  const [
    weeks,
    setWeeks,
  ] = useState(8);

  const [
    startDate,
    setStartDate,
  ] = useState(todayIso());

  const [
    planPreview,
    setPlanPreview,
  ] = useState<
    StrengthPlanPreviewResponse | null
  >(null);

  const [
    previewingPlan,
    setPreviewingPlan,
  ] = useState(false);

  const [
    creatingPlan,
    setCreatingPlan,
  ] = useState(false);

  const [
    setDrafts,
    setSetDrafts,
  ] = useState<
    Record<string, SetDraft[]>
  >({});

  const [
    duration,
    setDuration,
  ] = useState("");

  const [
    notes,
    setNotes,
  ] = useState("");

  const [
    logging,
    setLogging,
  ] = useState(false);

  const [
    loggedWorkout,
    setLoggedWorkout,
  ] = useState<StrengthWorkout | null>(
    null,
  );

  const [
    outcome,
    setOutcome,
  ] = useState<
    StrengthWorkoutOutcome | null
  >(null);

  const [
    progression,
    setProgression,
  ] = useState<
    StrengthProgressionPreviewResponse | null
  >(null);

  const [
    applyingExerciseId,
    setApplyingExerciseId,
  ] = useState<string | null>(
    null,
  );

  const [
    appliedExerciseIds,
    setAppliedExerciseIds,
  ] = useState<Record<string, boolean>>(
    {},
  );


  const loadPlan = useCallback(
    async () => {
      if (!accessToken) {
        return;
      }

      setLoading(true);
      setError(null);

      try {
        const plans = await getStrengthPlans(
          accessToken,
        );

        const active = plans.items.find(
          (item) =>
            item.status === "active",
        );

        if (!active) {
          setDetail(null);
          return;
        }

        const response =
          await getStrengthPlanDetail(
            active.id,
            accessToken,
          );

        setDetail(response);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : (
                "Non riesco a caricare " +
                "il programma palestra."
              ),
        );
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );


  useEffect(() => {
    void loadPlan();
  }, [loadPlan]);


  const nextWorkout = useMemo(
    () => {
      if (!detail) {
        return null;
      }

      return (
        [...detail.workouts]
          .filter(
            (item) =>
              item.status === "planned",
          )
          .sort(
            (left, right) =>
              left.scheduled_date.localeCompare(
                right.scheduled_date,
              ),
          )[0] ?? null
      );
    },
    [detail],
  );


  useEffect(() => {
    if (!nextWorkout) {
      setSetDrafts({});
      return;
    }

    setSetDrafts(
      initialDrafts(nextWorkout),
    );

    setDuration(
      nextWorkout
        .estimated_duration_minutes != null
        ? String(
            nextWorkout
              .estimated_duration_minutes,
          )
        : "",
    );

    setNotes("");
  }, [nextWorkout]);


  async function previewPlan() {
    if (!accessToken) {
      return;
    }

    setPreviewingPlan(true);
    setError(null);
    setMessage(null);

    try {
      const response =
        await previewStrengthPlan(
          {
            start_date: startDate,
            goal,
            experience_level: experience,
            sessions_per_week: sessions,
            total_weeks: weeks,
          },
          accessToken,
        );

      setPlanPreview(response);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
              "Non riesco a creare " +
              "l'anteprima."
            ),
      );
    } finally {
      setPreviewingPlan(false);
    }
  }


  async function confirmPlan() {
    if (
      !accessToken ||
      !planPreview
    ) {
      return;
    }

    setCreatingPlan(true);
    setError(null);
    setMessage(null);

    try {
      await createStrengthPlan(
        {
          start_date: startDate,
          goal,
          experience_level: experience,
          sessions_per_week: sessions,
          total_weeks: weeks,
        },
        accessToken,
      );

      setPlanPreview(null);

      setMessage(
        "Programma palestra creato.",
      );

      await loadPlan();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
              "Non riesco a creare " +
              "il programma palestra."
            ),
      );
    } finally {
      setCreatingPlan(false);
    }
  }


  function updateSet(
    exerciseId: string,
    setIndex: number,
    field: keyof SetDraft,
    value: string,
  ) {
    setSetDrafts(
      (current) => ({
        ...current,
        [exerciseId]: (
          current[exerciseId] ?? []
        ).map(
          (item, index) =>
            index === setIndex
              ? {
                  ...item,
                  [field]: value,
                }
              : item,
        ),
      }),
    );
  }


  async function submitWorkout() {
    if (
      !accessToken ||
      !nextWorkout
    ) {
      return;
    }

    setLogging(true);
    setError(null);
    setMessage(null);
    setOutcome(null);
    setProgression(null);
    setAppliedExerciseIds({});

    try {
      const exercises =
        nextWorkout.exercises.map(
          (exercise) => {
            const drafts =
              setDrafts[exercise.id] ?? [];

            if (!drafts.length) {
              throw new Error(
                (
                  `Inserisci almeno una serie ` +
                  `per ${exercise.exercise_name}.`
                ),
              );
            }

            return {
              exercise_id: exercise.id,
              sets: drafts.map(
                (item) => {
                  const reps =
                    Number(item.reps);

                  const loadKg =
                    item.loadKg.trim()
                      ? Number(item.loadKg)
                      : 0;

                  const rir =
                    item.rir.trim()
                      ? Number(item.rir)
                      : null;

                  if (
                    !Number.isFinite(reps) ||
                    reps <= 0
                  ) {
                    throw new Error(
                      (
                        `Ripetizioni non valide ` +
                        `per ${exercise.exercise_name}.`
                      ),
                    );
                  }

                  if (
                    !Number.isFinite(loadKg) ||
                    loadKg < 0
                  ) {
                    throw new Error(
                      (
                        `Carico non valido per ` +
                        `${exercise.exercise_name}.`
                      ),
                    );
                  }

                  if (
                    rir != null &&
                    (
                      !Number.isFinite(rir) ||
                      rir < 0 ||
                      rir > 6
                    )
                  ) {
                    throw new Error(
                      (
                        `RIR non valido per ` +
                        `${exercise.exercise_name}.`
                      ),
                    );
                  }

                  return {
                    reps,
                    load_kg: loadKg,
                    rir,
                  };
                },
              ),
            };
          },
        );

      await logStrengthWorkout(
        nextWorkout.id,
        {
          performed_date: todayIso(),
          duration_minutes:
            duration.trim()
              ? Number(duration)
              : null,
          notes:
            notes.trim() || null,
          exercises,
        },
        accessToken,
      );

      const [
        outcomeResponse,
        progressionResponse,
      ] = await Promise.all([
        getStrengthWorkoutOutcome(
          nextWorkout.id,
          accessToken,
        ),
        getStrengthProgressionPreview(
          nextWorkout.id,
          accessToken,
        ),
      ]);

      setLoggedWorkout(nextWorkout);

      setOutcome(
        outcomeResponse.outcome,
      );

      setProgression(
        progressionResponse,
      );

      setMessage(
        "Seduta registrata.",
      );

      await loadPlan();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
              "Non riesco a registrare " +
              "la seduta."
            ),
      );
    } finally {
      setLogging(false);
    }
  }


  async function applyProgression(
    exerciseId: string,
  ) {
    if (
      !accessToken ||
      !loggedWorkout
    ) {
      return;
    }

    setApplyingExerciseId(
      exerciseId,
    );

    setError(null);

    try {
      await applyStrengthProgression(
        loggedWorkout.id,
        exerciseId,
        accessToken,
      );

      setAppliedExerciseIds(
        (current) => ({
          ...current,
          [exerciseId]: true,
        }),
      );

      setMessage(
        "Progressione applicata.",
      );

      await loadPlan();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : (
              "Non riesco ad applicare " +
              "la progressione."
            ),
      );
    } finally {
      setApplyingExerciseId(null);
    }
  }


  return (
    <section className={styles.section}>
      <div className={styles.heading}>
        <div>
          <p className={styles.eyebrow}>
            Palestra
          </p>

          <h2>
            Programma forza
          </h2>

          <p>
            Piano, seduta reale e
            progressione dei carichi nello
            stesso flusso.
          </p>
        </div>

        {detail ? (
          <span className={styles.activeBadge}>
            Piano attivo
          </span>
        ) : null}
      </div>


      {error ? (
        <div className={styles.error}>
          {error}
        </div>
      ) : null}

      {message ? (
        <div className={styles.message}>
          {message}
        </div>
      ) : null}


      {loading ? (
        <div className={styles.empty}>
          Carico il programma palestra…
        </div>
      ) : !detail ? (
        <div className={styles.builder}>
          <div className={styles.builderIntro}>
            <strong>
              Crea il tuo programma
            </strong>

            <span>
              La struttura viene generata
              in modo deterministico.
            </span>
          </div>

          <div className={styles.formGrid}>
            <label>
              Obiettivo
              <select
                value={goal}
                onChange={(event) =>
                  setGoal(
                    event.target
                      .value as StrengthGoal,
                  )
                }
              >
                <option value="hypertrophy">
                  Ipertrofia
                </option>
                <option value="strength">
                  Forza
                </option>
                <option value="general_fitness">
                  Fitness generale
                </option>
              </select>
            </label>

            <label>
              Esperienza
              <select
                value={experience}
                onChange={(event) =>
                  setExperience(
                    event.target
                      .value as StrengthExperience,
                  )
                }
              >
                <option value="beginner">
                  Principiante
                </option>
                <option value="intermediate">
                  Intermedio
                </option>
                <option value="advanced">
                  Avanzato
                </option>
              </select>
            </label>

            <label>
              Sedute / settimana
              <select
                value={sessions}
                onChange={(event) =>
                  setSessions(
                    Number(
                      event.target.value,
                    ) as 2 | 3 | 4,
                  )
                }
              >
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={4}>4</option>
              </select>
            </label>

            <label>
              Durata programma
              <select
                value={weeks}
                onChange={(event) =>
                  setWeeks(
                    Number(
                      event.target.value,
                    ),
                  )
                }
              >
                <option value={4}>
                  4 settimane
                </option>
                <option value={6}>
                  6 settimane
                </option>
                <option value={8}>
                  8 settimane
                </option>
                <option value={10}>
                  10 settimane
                </option>
                <option value={12}>
                  12 settimane
                </option>
              </select>
            </label>

            <label>
              Prima seduta
              <input
                type="date"
                value={startDate}
                onChange={(event) =>
                  setStartDate(
                    event.target.value,
                  )
                }
              />
            </label>
          </div>

          <button
            type="button"
            className={styles.primaryButton}
            disabled={previewingPlan}
            onClick={() => {
              void previewPlan();
            }}
          >
            {previewingPlan
              ? "Genero…"
              : "Anteprima programma"}
          </button>

          {planPreview ? (
            <div className={styles.preview}>
              <div>
                <strong>
                  {
                    planPreview.plan
                      .workout_count
                  }{" "}
                  sedute
                </strong>

                <span>
                  {
                    planPreview.plan
                      .total_weeks
                  }{" "}
                  settimane ·{" "}
                  {
                    planPreview.plan
                      .sessions_per_week
                  }{" "}
                  / settimana
                </span>
              </div>

              <div
                className={
                  styles.previewWorkoutList
                }
              >
                {planPreview.plan.workouts
                  .slice(0, 4)
                  .map((workout) => (
                    <span
                      key={
                        workout.scheduled_date +
                        workout.title
                      }
                    >
                      {formatDate(
                        workout.scheduled_date,
                      )}
                      {" · "}
                      {workout.title}
                    </span>
                  ))}
              </div>

              <button
                type="button"
                className={
                  styles.primaryButton
                }
                disabled={creatingPlan}
                onClick={() => {
                  void confirmPlan();
                }}
              >
                {creatingPlan
                  ? "Creo programma…"
                  : "Conferma programma"}
              </button>
            </div>
          ) : null}
        </div>
      ) : (
        <>
          <div className={styles.planSummary}>
            <div>
              <span>Obiettivo</span>
              <strong>
                {goalLabel(
                  detail.plan.goal,
                )}
              </strong>
            </div>

            <div>
              <span>Livello</span>
              <strong>
                {experienceLabel(
                  detail.plan
                    .experience_level,
                )}
              </strong>
            </div>

            <div>
              <span>Frequenza</span>
              <strong>
                {
                  detail.plan
                    .sessions_per_week
                }
                × settimana
              </strong>
            </div>

            <div>
              <span>Durata</span>
              <strong>
                {detail.plan.total_weeks}
                {" "}settimane
              </strong>
            </div>
          </div>


          <StrengthProgramOverview
            detail={detail}
            refreshKey={
              loggedWorkout
                ? 1
                : 0
            }
          />

          {nextWorkout ? (
            <div className={styles.workoutCard}>
              <div
                className={
                  styles.workoutHeader
                }
              >
                <div>
                  <span
                    className={
                      styles.workoutDate
                    }
                  >
                    Prossima seduta ·{" "}
                    {formatDate(
                      nextWorkout
                        .scheduled_date,
                    )}
                  </span>

                  <h3>
                    {nextWorkout.title}
                  </h3>

                  <p>
                    Settimana{" "}
                    {
                      nextWorkout
                        .training_week
                    }
                    {" · "}
                    {nextWorkout.focus}
                  </p>
                </div>

                {nextWorkout
                  .estimated_duration_minutes !=
                null ? (
                  <strong>
                    ~
                    {
                      nextWorkout
                        .estimated_duration_minutes
                    }{" "}
                    min
                  </strong>
                ) : null}
              </div>


              <div
                className={
                  styles.exerciseList
                }
              >
                {nextWorkout.exercises.map(
                  (exercise) => (
                    <article
                      key={exercise.id}
                      className={
                        styles.exerciseCard
                      }
                    >
                      <div
                        className={
                          styles.exerciseHeader
                        }
                      >
                        <div>
                          <span>
                            Esercizio{" "}
                            {exercise.position}
                          </span>

                          <h4>
                            {
                              exercise
                                .exercise_name
                            }
                          </h4>
                        </div>

                        <div
                          className={
                            styles.target
                          }
                        >
                          <strong>
                            {
                              exercise
                                .target_sets
                            }
                            {" × "}
                            {
                              exercise
                                .target_reps_min
                            }
                            –
                            {
                              exercise
                                .target_reps_max
                            }
                          </strong>

                          <span>
                            RIR{" "}
                            {
                              exercise
                                .target_rir ??
                              "—"
                            }
                            {" · "}
                            {exercise
                              .prescribed_load_kg !=
                            null
                              ? (
                                  `${
                                    exercise
                                      .prescribed_load_kg
                                  } kg`
                                )
                              : (
                                  "carico libero"
                                )}
                          </span>
                        </div>
                      </div>

                      <div
                        className={
                          styles.setTable
                        }
                      >
                        <div
                          className={
                            styles.setHeader
                          }
                        >
                          <span>Serie</span>
                          <span>Reps</span>
                          <span>Kg</span>
                          <span>RIR</span>
                        </div>

                        {(
                          setDrafts[
                            exercise.id
                          ] ?? []
                        ).map(
                          (
                            setItem,
                            setIndex,
                          ) => (
                            <div
                              key={
                                setIndex
                              }
                              className={
                                styles.setRow
                              }
                            >
                              <strong>
                                {setIndex + 1}
                              </strong>

                              <input
                                type="number"
                                min="1"
                                value={
                                  setItem.reps
                                }
                                onChange={(
                                  event,
                                ) =>
                                  updateSet(
                                    exercise.id,
                                    setIndex,
                                    "reps",
                                    event
                                      .target
                                      .value,
                                  )
                                }
                              />

                              <input
                                type="number"
                                min="0"
                                step="0.5"
                                placeholder="0"
                                value={
                                  setItem.loadKg
                                }
                                onChange={(
                                  event,
                                ) =>
                                  updateSet(
                                    exercise.id,
                                    setIndex,
                                    "loadKg",
                                    event
                                      .target
                                      .value,
                                  )
                                }
                              />

                              <input
                                type="number"
                                min="0"
                                max="6"
                                step="1"
                                value={
                                  setItem.rir
                                }
                                onChange={(
                                  event,
                                ) =>
                                  updateSet(
                                    exercise.id,
                                    setIndex,
                                    "rir",
                                    event
                                      .target
                                      .value,
                                  )
                                }
                              />
                            </div>
                          ),
                        )}
                      </div>
                    </article>
                  ),
                )}
              </div>


              <div className={styles.logMeta}>
                <label>
                  Durata reale
                  <div
                    className={
                      styles.unitInput
                    }
                  >
                    <input
                      type="number"
                      min="1"
                      value={duration}
                      onChange={(event) =>
                        setDuration(
                          event.target.value,
                        )
                      }
                    />
                    <span>min</span>
                  </div>
                </label>

                <label>
                  Note
                  <input
                    value={notes}
                    placeholder="Opzionale"
                    onChange={(event) =>
                      setNotes(
                        event.target.value,
                      )
                    }
                  />
                </label>
              </div>

              <button
                type="button"
                className={
                  styles.primaryButton
                }
                disabled={logging}
                onClick={() => {
                  void submitWorkout();
                }}
              >
                {logging
                  ? "Registro seduta…"
                  : "Completa seduta"}
              </button>
            </div>
          ) : (
            <div className={styles.empty}>
              Non ci sono altre sedute
              pianificate in questo programma.
            </div>
          )}
        </>
      )}


      {loggedWorkout && outcome ? (
        <div className={styles.resultCard}>
          <div className={styles.resultHeader}>
            <div>
              <span>
                Outcome seduta
              </span>

              <h3>
                {loggedWorkout.title}
              </h3>
            </div>

            <strong>
              {outcomeLabel(
                outcome.outcome,
              )}
            </strong>
          </div>

          <p>
            {outcome.message}
          </p>

          <div
            className={
              styles.outcomeExercises
            }
          >
            {outcome.exercises.map(
              (exercise) => (
                <div
                  key={
                    exercise.exercise_id
                  }
                  className={
                    styles.outcomeRow
                  }
                >
                  <div>
                    <strong>
                      {
                        exercise
                          .exercise_name
                      }
                    </strong>

                    <span>
                      {exercise.message}
                    </span>
                  </div>

                  <span>
                    {outcomeLabel(
                      exercise.outcome,
                    )}
                  </span>
                </div>
              ),
            )}
          </div>
        </div>
      ) : null}


      {loggedWorkout &&
      progression?.status === "preview" ? (
        <div className={styles.resultCard}>
          <div className={styles.resultHeader}>
            <div>
              <span>
                Progressive overload
              </span>

              <h3>
                Prossima esposizione
              </h3>
            </div>
          </div>

          <div
            className={
              styles.progressionList
            }
          >
            {progression.proposals.map(
              (proposal) => {
                const applied =
                  appliedExerciseIds[
                    proposal.exercise_id
                  ];

                return (
                  <div
                    key={
                      proposal.exercise_id
                    }
                    className={
                      styles.progressionRow
                    }
                  >
                    <div>
                      <strong>
                        {
                          proposal
                            .exercise_name
                        }
                      </strong>

                      <span>
                        {actionLabel(
                          proposal.action,
                        )}
                        {" · "}
                        {
                          proposal
                            .current_load_kg
                        }{" "}
                        →{" "}
                        {
                          proposal
                            .proposed_load_kg
                        }{" "}
                        kg
                      </span>

                      <small>
                        {proposal.message}
                      </small>
                    </div>

                    {proposal.next_exposure &&
                    proposal.current_load_kg >
                      0 ? (
                      <button
                        type="button"
                        disabled={
                          applied ||
                          applyingExerciseId ===
                            proposal.exercise_id
                        }
                        onClick={() => {
                          void applyProgression(
                            proposal.exercise_id,
                          );
                        }}
                      >
                        {applied
                          ? "Applicata"
                          : applyingExerciseId ===
                              proposal.exercise_id
                            ? "Applico…"
                            : "Applica"}
                      </button>
                    ) : (
                      <span
                        className={
                          styles.noAction
                        }
                      >
                        Nessuna modifica
                      </span>
                    )}
                  </div>
                );
              },
            )}
          </div>
        </div>
      ) : null}
    </section>
  );
}
