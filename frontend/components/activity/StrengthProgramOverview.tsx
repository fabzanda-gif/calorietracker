"use client";

import {
  useEffect,
  useMemo,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";

import {
  getStrengthPlanHistory,
  type StrengthPlanDetailResponse,
  type StrengthPlanHistoryResponse,
} from "@/lib/api/strength";

import styles from "./StrengthProgramOverview.module.css";


function formatDate(value: string): string {
  return new Date(
    `${value}T00:00:00`,
  ).toLocaleDateString(
    "it-IT",
    {
      day: "numeric",
      month: "short",
    },
  );
}


function statusLabel(
  value: string,
): string {
  if (value === "completed") {
    return "Completata";
  }

  if (value === "skipped") {
    return "Saltata";
  }

  return "Pianificata";
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


function progressionLabel(
  value: string,
): string {
  if (value === "increase_load") {
    return "Carico aumentato";
  }

  if (value === "reduce_load") {
    return "Carico ridotto";
  }

  return "Carico mantenuto";
}


export function StrengthProgramOverview({
  detail,
  refreshKey = 0,
}: {
  detail: StrengthPlanDetailResponse;
  refreshKey?: number;
}) {
  const { accessToken } = useAuth();

  const [
    history,
    setHistory,
  ] = useState<
    StrengthPlanHistoryResponse | null
  >(null);

  const [
    historyError,
    setHistoryError,
  ] = useState<string | null>(null);

  const [
    loadingHistory,
    setLoadingHistory,
  ] = useState(false);


  useEffect(() => {
    if (!accessToken) {
      return;
    }

    let active = true;

    async function loadHistory() {
      setLoadingHistory(true);
      setHistoryError(null);

      try {
        const response =
          await getStrengthPlanHistory(
            detail.plan.id,
            accessToken,
          );

        if (active) {
          setHistory(response);
        }
      } catch (err) {
        if (active) {
          setHistoryError(
            err instanceof Error
              ? err.message
              : (
                  "Non riesco a caricare " +
                  "lo storico palestra."
                ),
          );
        }
      } finally {
        if (active) {
          setLoadingHistory(false);
        }
      }
    }

    void loadHistory();

    return () => {
      active = false;
    };
  }, [
    accessToken,
    detail.plan.id,
    refreshKey,
  ]);


  const weeks = useMemo(() => {
    const grouped = new Map<
      number,
      typeof detail.workouts
    >();

    for (const workout of detail.workouts) {
      const week = Number(
        workout.training_week,
      );

      const current =
        grouped.get(week) ?? [];

      current.push(workout);

      grouped.set(
        week,
        current,
      );
    }

    return [...grouped.entries()]
      .sort(
        ([left], [right]) =>
          left - right,
      )
      .map(
        ([week, workouts]) => ({
          week,
          workouts: [...workouts].sort(
            (left, right) =>
              left.scheduled_date.localeCompare(
                right.scheduled_date,
              ),
          ),
        }),
      );
  }, [detail.workouts]);


  return (
    <div className={styles.wrapper}>
      <section className={styles.block}>
        <div className={styles.heading}>
          <div>
            <span>Programma completo</span>
            <h3>
              Tutte le settimane
            </h3>
          </div>

          <strong>
            {detail.workout_count} sedute
          </strong>
        </div>

        <div className={styles.weeks}>
          {weeks.map(
            ({ week, workouts }) => (
              <article
                key={week}
                className={styles.week}
              >
                <div
                  className={
                    styles.weekHeading
                  }
                >
                  <strong>
                    Settimana {week}
                  </strong>

                  <span>
                    {
                      workouts.filter(
                        (item) =>
                          item.status ===
                          "completed",
                      ).length
                    }
                    /{workouts.length} completate
                  </span>
                </div>

                <div
                  className={
                    styles.workoutList
                  }
                >
                  {workouts.map(
                    (workout) => (
                      <div
                        key={workout.id}
                        className={
                          styles.workout
                        }
                      >
                        <div>
                          <span>
                            {formatDate(
                              workout
                                .scheduled_date,
                            )}
                          </span>

                          <strong>
                            {workout.title}
                          </strong>

                          <small>
                            {
                              workout.exercises
                                .length
                            }{" "}
                            esercizi
                            {" · "}
                            {workout.focus}
                          </small>
                        </div>

                        <span
                          className={
                            styles.status
                          }
                        >
                          {statusLabel(
                            workout.status,
                          )}
                        </span>
                      </div>
                    ),
                  )}
                </div>
              </article>
            ),
          )}
        </div>
      </section>


      <section className={styles.block}>
        <div className={styles.heading}>
          <div>
            <span>Storico palestra</span>
            <h3>
              Sedute completate
            </h3>
          </div>

          {history ? (
            <strong>
              {history.count}
            </strong>
          ) : null}
        </div>

        {loadingHistory ? (
          <div className={styles.empty}>
            Carico lo storico…
          </div>
        ) : historyError ? (
          <div className={styles.error}>
            {historyError}
          </div>
        ) : !history?.items.length ? (
          <div className={styles.empty}>
            Nessuna seduta completata ancora.
          </div>
        ) : (
          <div className={styles.history}>
            {history.items.map(
              (item) => (
                <article
                  key={item.workout.id}
                  className={
                    styles.historyCard
                  }
                >
                  <div
                    className={
                      styles.historyHeader
                    }
                  >
                    <div>
                      <span>
                        {formatDate(
                          item.workout_log
                            .performed_date,
                        )}
                      </span>

                      <h4>
                        {item.workout.title}
                      </h4>

                      <small>
                        {item.workout_log
                          .duration_minutes !=
                        null
                          ? (
                              `${
                                item.workout_log
                                  .duration_minutes
                              } min`
                            )
                          : "Durata non indicata"}
                      </small>
                    </div>

                    <strong>
                      {outcomeLabel(
                        item.outcome.outcome,
                      )}
                    </strong>
                  </div>

                  {item.workout_log.notes ? (
                    <p className={styles.notes}>
                      {item.workout_log.notes}
                    </p>
                  ) : null}

                  <div
                    className={
                      styles.exerciseHistory
                    }
                  >
                    {item.exercises.map(
                      (exercise) => (
                        <div
                          key={exercise.id}
                          className={
                            styles.exercise
                          }
                        >
                          <strong>
                            {
                              exercise
                                .exercise_name
                            }
                          </strong>

                          <div
                            className={
                              styles.sets
                            }
                          >
                            {exercise.sets.map(
                              (setItem) => (
                                <span
                                  key={
                                    setItem
                                      .set_index
                                  }
                                >
                                  {
                                    setItem
                                      .reps
                                  }
                                  {" × "}
                                  {
                                    setItem
                                      .load_kg
                                  }
                                  {" kg"}
                                  {setItem.rir !=
                                  null
                                    ? (
                                        ` · RIR ${
                                          setItem
                                            .rir
                                        }`
                                      )
                                    : ""}
                                </span>
                              ),
                            )}
                          </div>
                        </div>
                      ),
                    )}
                  </div>

                  {item.progressions.length ? (
                    <div
                      className={
                        styles.progressions
                      }
                    >
                      {item.progressions.map(
                        (progression) => (
                          <div
                            key={
                              progression.id
                            }
                          >
                            <strong>
                              {progressionLabel(
                                progression.action,
                              )}
                            </strong>

                            <span>
                              {
                                progression
                                  .exercise_key
                              }
                              {" · "}
                              {
                                progression
                                  .observed_load_kg ??
                                "—"
                              }
                              {" → "}
                              {
                                progression
                                  .after_load_kg ??
                                "—"
                              }
                              {" kg"}
                            </span>
                          </div>
                        ),
                      )}
                    </div>
                  ) : null}
                </article>
              ),
            )}
          </div>
        )}
      </section>
    </div>
  );
}
