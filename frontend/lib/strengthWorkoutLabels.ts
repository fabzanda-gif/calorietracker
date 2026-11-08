import type { StrengthWorkoutExercise } from "./api/strength";

// Match the exercise prescription, including existing plans, without renaming stored records.
type Prescription = Pick<StrengthWorkoutExercise, "exercise_key" | "exercise_name" | "movement_pattern" | "position">;

export function exerciseMuscles(exercise: Prescription): string[] {
  const name = `${exercise.exercise_key} ${exercise.exercise_name}`.toLowerCase();
  if (/hip.thrust|glute|glutei/.test(name)) return ["Glutei"];
  if (/lateral.raise|alzate|shoulder|spalle/.test(name)) return ["Spalle"];
  if (/bicep|bicip|curl/.test(name) && !/leg|hamstring/.test(name)) return ["Bicipiti"];
  if (/tricep|tricip/.test(name)) return ["Tricipiti"];
  const patterns: Record<string, string[]> = {
    squat: ["Gambe", "Glutei"], single_leg: ["Gambe", "Glutei"],
    hinge: ["Gambe", "Glutei"], horizontal_push: ["Petto"],
    vertical_push: ["Spalle"], horizontal_pull: ["Schiena"],
    vertical_pull: ["Schiena"], core: ["Addome"],
  };
  return patterns[exercise.movement_pattern] ?? [];
}

export function workoutMuscles(workout: { exercises: Prescription[] }): string[] {
  return [...new Set([...(workout.exercises ?? [])].sort((a, b) => a.position - b.position).flatMap(exerciseMuscles))];
}

export function workoutTitle(workout: { exercises: Prescription[] }): string {
  return workoutMuscles(workout).join(" · ") || "Allenamento in palestra";
}
