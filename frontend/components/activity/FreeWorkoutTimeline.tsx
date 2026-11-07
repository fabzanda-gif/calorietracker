"use client";

import { useEffect, useState } from "react";
import {
  getRecentFreeStrengthWorkouts,
  getStrengthWorkoutDetail,
  type FreeWorkoutRecentItem,
  type StrengthWorkoutDetailResponse,
} from "@/lib/api/strength";

import styles from "./FreeWorkoutTimeline.module.css";

interface Props {
  accessToken: string;
  refreshKey: number;
  activeWorkoutId?: string | null;
  onResume: (workoutId: string, performedDate: string) => Promise<void>;
}

export function FreeWorkoutTimeline({
  accessToken,
  refreshKey,
  activeWorkoutId,
  onResume,
}: Props) {
  const [items, setItems] = useState<FreeWorkoutRecentItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<StrengthWorkoutDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getRecentFreeStrengthWorkouts(accessToken)
      .then((result) => {
        if (active) setItems(result.items);
      })
      .catch(() => {
        if (active) setError("Non riesco a caricare lo storico dei workout liberi.");
      });
    return () => { active = false; };
  }, [accessToken, refreshKey]);

  async function resume(item: FreeWorkoutRecentItem) {
    if (busyId) return;
    setBusyId(item.workout.id);
    setError(null);
    try {
      await onResume(
        item.workout.id,
        item.workout_log?.performed_date ?? item.workout.scheduled_date,
      );
    } catch {
      setError("Non riesco a riprendere questa seduta.");
    } finally {
      setBusyId(null);
    }
  }

  async function showDetails(item: FreeWorkoutRecentItem) {
    if (busyId) return;
    if (expanded?.workout.id === item.workout.id) {
      setExpanded(null);
      return;
    }
    setBusyId(item.workout.id);
    setError(null);
    try {
      setExpanded(await getStrengthWorkoutDetail(item.workout.id, accessToken));
    } catch {
      setError("Non riesco ad aprire il dettaglio della seduta.");
    } finally {
      setBusyId(null);
    }
  }

  const drafts = items.filter(
    (item) => item.workout.status === "planned" &&
      item.workout_log?.status !== "completed",
  );
  const completed = items.filter(
    (item) => item.workout.status === "completed" ||
      item.workout_log?.status === "completed",
  );

  return (
    <section className={styles.timeline} aria-labelledby="free-workout-history">
      <div className={styles.heading}>
        <h3 id="free-workout-history">I tuoi workout liberi</h3>
        <span>{items.length} recenti</span>
      </div>
      {drafts.length > 0 && (
        <>
          <h4>Da riprendere</h4>
          <ul className={styles.list}>
            {drafts.map((item) => (
              <li key={item.workout.id} className={styles.item}>
                <div>
                  <strong>{item.workout.title}</strong>
                  <small>{item.workout_log?.performed_date ?? item.workout.scheduled_date} · In corso</small>
                </div>
                <button
                  type="button"
                  disabled={busyId !== null || item.workout.id === activeWorkoutId}
                  onClick={() => void resume(item)}
                >
                  {item.workout.id === activeWorkoutId ? "Aperto" : "Riprendi"}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      <h4>Sedute completate</h4>
      {completed.length === 0 ? (
        <p className={styles.muted}>Nessun workout libero completato.</p>
      ) : (
        <ul className={styles.list}>
          {completed.map((item) => (
            <li className={styles.item} key={item.workout.id}>
              <div>
                <strong>{item.workout.title}</strong>
                <small>
                  {item.workout_log?.performed_date ?? item.workout.scheduled_date}
                  {item.workout_log?.duration_minutes
                    ? ` · ${item.workout_log.duration_minutes} min` : ""}
                </small>
              </div>
              <button
                type="button"
                disabled={busyId !== null}
                onClick={() => void showDetails(item)}
                aria-expanded={expanded?.workout.id === item.workout.id}
              >Dettagli</button>
            </li>
          ))}
        </ul>
      )}
      {expanded && (
        <div className={styles.details}>
          <h4>{expanded.workout.title}</h4>
          <p>{expanded.workout_log?.notes || "Nessuna nota"}</p>
          {expanded.workout.exercises.map((exercise) => {
            const sets = expanded.sets.filter(
              (set) => set.strength_workout_exercise_id === exercise.id,
            );
            return (
              <div key={exercise.id}>
                <strong>{exercise.exercise_name}</strong>
                <p>
                  {sets.length > 0
                    ? sets.map((set) =>
                        `${set.reps} rip. × ${set.load_kg} kg`,
                      ).join(" · ")
                    : "Nessuna serie registrata"}
                </p>
              </div>
            );
          })}
        </div>
      )}
      {error && <p className={styles.error} role="alert">{error}</p>}
    </section>
  );
}
