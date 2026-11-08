import { exerciseRef, type StrengthLoadProfile } from "./api/strengthLoads";
import type { StrengthEffortFeeling, StrengthPlanHistoryItem, StrengthWorkoutExercise } from "./api/strength";

export type LoadReference = {
  exerciseId: string | null;
  key: string;
  name: string;
  date: string;
  loadKg: number;
  reps: number;
  rir: number;
};
export type LoadAdvice = { reps: number; loadKg: number | null; source: "plan" | "history" | "profile" | "bodyweight" | "calibration"; estimatedMaxKg?: number };

export function suggestedReps(exercise: StrengthWorkoutExercise): number {
  return Math.floor((exercise.target_reps_min + exercise.target_reps_max) / 2);
}
export function effortReserve(feeling: StrengthEffortFeeling | null | undefined): number {
  return feeling === "easy" ? 4 : feeling === "hard" ? 1 : feeling === "too_hard" ? 0 : 2;
}
export function roundLoadDown(value: number): number { return Math.floor(value * 2 + 1e-8) / 2; }
export function estimatedMax(loadKg: number, reps: number, rir: number): number | undefined {
  if (!(loadKg > 0) || reps < 1 || reps > 12) return undefined;
  return Math.round(loadKg * (1 + (reps + Math.max(0, Math.min(4, rir))) / 30) * 10) / 10;
}
export function isUnloadedExercise(exercise: StrengthWorkoutExercise): boolean {
  return /(^|[ _-])(plank|dead_bug|bird_dog)([ _-]|$)/.test(exercise.exercise_key.toLowerCase());
}
export function weightConvention(exercise: StrengthWorkoutExercise): string {
  if (/dumbbell|manubr/.test(`${exercise.exercise_key} ${exercise.exercise_name}`.toLowerCase())) return "Kg per singolo manubrio: usa sempre la stessa convenzione.";
  return "Bilanciere: peso totale, barra inclusa. Macchina: peso indicato sul pacco pesi. Usa sempre la stessa attrezzatura e convenzione.";
}
export function referencesFromHistory(items: StrengthPlanHistoryItem[]): LoadReference[] {
  const references: LoadReference[] = [];
  for (const item of items) {
    for (const exercise of item.exercises) {
      const sets = exercise.sets.filter((set) => Number.isFinite(set.load_kg) && set.load_kg >= 0 && set.reps > 0 && set.reps <= 30);
      if (!sets.length) continue;
      // Use the lowest working load of the latest session; never infer a heavier load from a warm-up or best set.
      const set = [...sets].sort((a, b) => a.load_kg - b.load_kg)[0];
      references.push({ exerciseId: exercise.exercise_id ?? null, key: exercise.exercise_key, name: exercise.exercise_name,
        date: `${item.workout_log.performed_date}T${item.workout_log.id}`, loadKg: set.load_kg, reps: set.reps,
        rir: set.rir ?? effortReserve((set as typeof set & { feeling?: StrengthEffortFeeling }).feeling) });
    }
  }
  return references.sort((a, b) => b.date.localeCompare(a.date));
}
export function loadAdvice(exercise: StrengthWorkoutExercise, references: LoadReference[], profiles: StrengthLoadProfile[] = []): LoadAdvice {
  const reps = suggestedReps(exercise);
  if (exercise.prescribed_load_kg != null) return { reps, loadKg: exercise.prescribed_load_kg, source: "plan" };
  const reference = references.find((item) => exercise.exercise_id && item.exerciseId
    ? exercise.exercise_id === item.exerciseId
    : item.key === exercise.exercise_key && item.name.toLowerCase() === exercise.exercise_name.toLowerCase());
  const profile = profiles.find((item) => item.exercise_ref === exerciseRef(exercise));
  if (profile && (!reference || profile.updated_at.slice(0, 10) >= reference.date.slice(0, 10))) {
    const max = profile.one_rep_max_kg;
    const recommended = max == null ? profile.working_load_kg : Math.min(1000, roundLoadDown(max / (1 + (reps + (exercise.target_rir ?? 2)) / 30)));
    return { reps, loadKg: profile.source === "known_max" ? recommended : Math.min(profile.working_load_kg, recommended), source: "profile", estimatedMaxKg: max ?? undefined };
  }
  if (reference) {
    const max = estimatedMax(reference.loadKg, reference.reps, reference.rir);
    const targetRir = exercise.target_rir ?? 2;
    const loadKg = max == null ? reference.loadKg : Math.max(0, roundLoadDown(Math.min(reference.loadKg, max / (1 + (reps + targetRir) / 30))));
    return { reps, loadKg, source: "history", estimatedMaxKg: max };
  }
  if (isUnloadedExercise(exercise)) return { reps, loadKg: 0, source: "bodyweight" };
  return { reps, loadKg: null, source: "calibration" };
}
