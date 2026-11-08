"use client";

import Link from "next/link";
import type { StrengthPlanDetailResponse } from "@/lib/api/strength";
import { workoutTitle } from "@/lib/strengthWorkoutLabels";
import styles from "./StrengthProgramOverview.module.css";

export function StrengthProgramOverview({ detail }: { detail: StrengthPlanDetailResponse; refreshKey?: number }) {
  const sessions = detail.workouts.filter((workout) => workout.training_week === 1);
  const completed = detail.workouts.filter((workout) => workout.status === "completed").length;
  return (
    <section className={styles.block}>
      <div className={styles.heading}>
        <div><span>La tua settimana tipo</span><h3>{detail.plan.sessions_per_week} allenamenti a settimana per {detail.plan.total_weeks} settimane</h3></div>
        <strong>{completed} / {detail.workout_count} completati</strong>
      </div>
      <div className={styles.workoutList}>
        {sessions.map((workout, index) => (
          <div key={workout.id} className={styles.workout}>
            <div><small>Allenamento {index + 1}</small><strong>{workoutTitle(workout)}</strong><small>{workout.exercises.length} esercizi{workout.estimated_duration_minutes ? ` · circa ${workout.estimated_duration_minutes} min` : ""}</small></div>
            <details><summary>Esercizi in ordine</summary><ol>{[...workout.exercises].sort((a, b) => a.position - b.position).map((exercise) => <li key={exercise.id}>{exercise.exercise_name} · {exercise.target_sets} × {exercise.target_reps_min}–{exercise.target_reps_max}</li>)}</ol></details>
          </div>
        ))}
      </div>
      <p><Link href={`/activities/workout/history/${detail.plan.id}`}>Vedi gli allenamenti completati →</Link></p>
    </section>
  );
}
