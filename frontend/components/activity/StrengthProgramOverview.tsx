"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/auth/AuthProvider";
import type { StrengthPlanDetailResponse, StrengthWorkoutExercise } from "@/lib/api/strength";
import { exerciseRef } from "@/lib/api/strengthLoads";
import { loadAdvice, roundLoadDown } from "@/lib/strengthRecommendations";
import { workoutTitle } from "@/lib/strengthWorkoutLabels";
import { useStrengthReferences } from "./useStrengthReferences";
import { StrengthLoadCalibration } from "./StrengthLoadCalibration";
import styles from "./StrengthProgramOverview.module.css";

function dayLabel(date: string) { return new Date(`${date}T00:00:00`).toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "short" }); }
export function StrengthProgramOverview({ detail }: { detail: StrengthPlanDetailResponse; refreshKey?: number }) {
  const { accessToken } = useAuth();
  const loads = useStrengthReferences(accessToken, detail.plan.id);
  const workouts = useMemo(() => [...detail.workouts].sort((a, b) => a.scheduled_date.localeCompare(b.scheduled_date) || (a.workout_index ?? 0) - (b.workout_index ?? 0)), [detail.workouts]);
  const next = workouts.find((workout) => workout.status === "planned");
  const [selectedId, setSelectedId] = useState(next?.id ?? workouts[0]?.id);
  const [calibrateId, setCalibrateId] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const selected = workouts.find((item) => item.id === selectedId) ?? next ?? workouts[0];
  const weeks = [...new Set(workouts.map((workout) => workout.training_week))];
  async function knownMax(exercise: StrengthWorkoutExercise, maxKg: number) {
    try {
      const advice = loadAdvice(exercise, []);
      await loads.save({ exercise_ref: exerciseRef(exercise), exercise_name: exercise.exercise_name, one_rep_max_kg: maxKg,
        working_load_kg: Math.min(1000, roundLoadDown(maxKg / (1 + (advice.reps + (exercise.target_rir ?? 2)) / 30))), reference_reps: advice.reps, reserve_reps: exercise.target_rir ?? 2, source: "known_max" });
      setCalibrateId(null); setSaveError(null); return true;
    } catch { setSaveError("Non riesco a salvare il massimale. Riprova."); return false; }
  }
  return <section className={styles.block}>
    <div className={styles.heading}><div><span>Il tuo programma</span><h3>{detail.plan.sessions_per_week} allenamenti a settimana per {detail.plan.total_weeks} settimane</h3></div><strong>{workouts.filter((workout) => workout.status === "completed").length} / {detail.workout_count} completati</strong></div>
    <p>Seleziona un giorno per vedere la scheda. Puoi consultare anche le sedute future senza iniziarle.</p>
    <div className={styles.calendar} aria-label="Giorni del programma">
      {weeks.map((week) => <div key={week ?? 0} className={styles.calendarWeek}><strong>Settimana {week}</strong><div>
        {workouts.filter((workout) => workout.training_week === week).map((workout) => <button key={workout.id} type="button" aria-pressed={selected?.id === workout.id} onClick={() => { setSelectedId(workout.id); setCalibrateId(null); setSaveError(null); }}>
          <span>{dayLabel(workout.scheduled_date)}</span><small>{workout.status === "completed" ? "Completato" : workout.status === "skipped" ? "Saltato" : workout.id === next?.id ? "Prossimo" : "In programma"}</small>
        </button>)}
      </div></div>)}
    </div>
    {selected ? <div className={styles.daySheet} aria-label="Scheda del giorno">
      <span>{dayLabel(selected.scheduled_date)}</span><h3>{workoutTitle(selected)}</h3>
      {loads.loading ? <p>Recupero i tuoi carichi…</p> : loads.error ? <p role="alert">{loads.error} <button type="button" onClick={loads.retry}>Riprova</button></p> : <>
        <div className={styles.tableScroll}><table><thead><tr><th>Ordine / esercizio</th><th>Serie × ripetizioni</th><th>Peso consigliato</th><th /></tr></thead><tbody>
          {[...selected.exercises].sort((a, b) => a.position - b.position).map((exercise, index) => { const advice = loadAdvice(exercise, loads.references, loads.profiles); return <tr key={exercise.id}>
            <td data-label="Esercizio">{index + 1}. {exercise.exercise_name}</td><td data-label="Serie e ripetizioni">{exercise.target_sets} × {advice.reps}<small>Fascia {exercise.target_reps_min}–{exercise.target_reps_max}</small></td>
            <td data-label="Peso consigliato">{advice.loadKg == null ? "Da impostare alla prima volta" : advice.loadKg === 0 ? "Corpo libero · 0 kg aggiunti" : `${advice.loadKg} kg`}<small>{advice.source === "plan" ? "Dal programma" : advice.source === "history" ? "Dalle tue ultime sedute" : advice.source === "profile" ? "Dal tuo riferimento salvato" : ""}</small></td>
            <td>{selected.status === "planned" && advice.source !== "bodyweight" && advice.source !== "plan" ? <button type="button" onClick={() => setCalibrateId(calibrateId === exercise.id ? null : exercise.id)}>Imposta massimale · {exercise.exercise_name}</button> : null}</td>
          </tr>; })}
        </tbody></table></div>
        {saveError ? <p role="alert">{saveError}</p> : null}
        {selected.exercises.filter((exercise) => exercise.id === calibrateId).map((exercise) => <StrengthLoadCalibration key={exercise.id} exercise={exercise} allowTest={false} onKnownMax={(max) => knownMax(exercise, max)} />)}
      </>}
      {next ? <p><Link className={styles.startButton} href={`/activities/workout/${detail.plan.id}/${next.id}`}>{selected.id === next.id ? "Inizia questo allenamento" : `Inizia il prossimo allenamento · ${dayLabel(next.scheduled_date)}`}</Link></p> : <p>Hai concluso tutte le sedute del programma.</p>}
    </div> : null}
    <p><Link href={`/activities/workout/history/${detail.plan.id}`}>Vedi gli allenamenti completati →</Link></p>
  </section>;
}
