"use client";

import {
  useEffect,
  useState,
} from "react";

import { useAuth } from "@/components/auth/AuthProvider";

import {
  getStrengthPlanHistory,
  type StrengthPlanDetailResponse,
  type StrengthPlanHistoryResponse,
} from "@/lib/api/strength";

import { workoutTitle } from "@/lib/strengthWorkoutLabels";
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


export function StrengthWorkoutHistory({
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


  return (
    <div className={styles.wrapper}>
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
                        {workoutTitle(detail.workouts.find((workout) => workout.id === item.workout.id) ?? item.workout)}
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
