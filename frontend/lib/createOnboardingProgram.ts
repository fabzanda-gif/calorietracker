import { createStrengthPlan, getStrengthPlanDetail, getStrengthPlans, type StrengthGoal, type StrengthExperience } from "./api/strength";
import { createRunningTrainingPlan, getTrainingPlans } from "./api/activities";
import { supabase } from "./supabase/client";

export type OnboardingProgramInput = {
  sport: "strength" | "running"; startDate: string; weeks: number; sessions: number;
  goal: StrengthGoal; experience: StrengthExperience; preferredDays: number[]; replace: boolean;
  currentKm: number; currentPace: number; targetKm: number; targetPace: number; longRunDay: number;
};
export function localIsoDate(value = new Date()): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}
export function addDays(value: string, days: number): string {
  const date = new Date(`${value}T12:00:00`); date.setDate(date.getDate() + days); return localIsoDate(date);
}
export async function createOnboardingProgram(input: OnboardingProgramInput, token: string): Promise<string> {
  if (input.sport === "running") {
    const target = addDays(input.startDate, input.weeks * 7);
    const plans = await getTrainingPlans(token);
    const existing = plans.items.find((plan) => plan.status === "active");
    const matching = existing && existing.start_date === input.startDate && existing.target_date === target && existing.sessions_per_week === input.sessions && existing.current_distance_meters === input.currentKm * 1000 && existing.target_distance_meters === input.targetKm * 1000 && existing.current_pace_seconds_per_km === input.currentPace && existing.target_pace_seconds_per_km === input.targetPace && existing.long_run_weekday === input.longRunDay;
    if (matching) return existing.id;
    if (existing && !input.replace) throw new Error("Hai già un programma corsa attivo. Se vuoi sostituirlo, seleziona la casella di sostituzione.");
    const result = await createRunningTrainingPlan({ start_date: input.startDate, target_date: target, sessions_per_week: input.sessions,
      current_distance_meters: input.currentKm * 1000, target_distance_meters: input.targetKm * 1000,
      current_pace_seconds_per_km: input.currentPace, target_pace_seconds_per_km: input.targetPace, long_run_weekday: input.longRunDay }, token, { replaceActive: input.replace });
    return result.plan.id;
  }
  const plans = await getStrengthPlans(token);
  const existing = plans.items.find((plan) => plan.status === "active");
  const matching = existing && existing.start_date === input.startDate && existing.sessions_per_week === input.sessions && existing.total_weeks === input.weeks && existing.goal === input.goal && existing.experience_level === input.experience;
  let id = matching ? existing.id : null;
  if (!id) {
    if (existing && !input.replace) throw new Error("Hai già un programma palestra attivo. Se vuoi sostituirlo, seleziona la casella di sostituzione.");
    const result = await createStrengthPlan({ start_date: input.startDate, goal: input.goal, experience_level: input.experience, sessions_per_week: input.sessions as 2 | 3 | 4, total_weeks: input.weeks, replace_active: input.replace }, token) as { plan: { id: string } };
    id = result.plan.id;
  }
  // Reconcile fixed weekdays before completing onboarding. A retry reuses the same plan.
  if (input.preferredDays.length) {
    const detail = await getStrengthPlanDetail(id, token);
    const startWeekday = new Date(`${input.startDate}T12:00:00`).getDay() || 7;
    const offsets = input.preferredDays.map((day) => (day - startWeekday + 7) % 7).sort((a, b) => a - b);
    const workouts = [...detail.workouts].sort((a, b) => (a.training_week ?? 0) - (b.training_week ?? 0) || (a.workout_index ?? 0) - (b.workout_index ?? 0));
    for (let i = 0; i < workouts.length; i += 4) await Promise.all(workouts.slice(i, i + 4).map(async (workout, index) => {
      const date = addDays(input.startDate, Math.floor((i + index) / input.sessions) * 7 + offsets[(i + index) % input.sessions]);
      if (workout.scheduled_date === date) return;
      if (workout.status !== "planned") throw new Error("Il programma contiene sedute già eseguite: i loro giorni non vengono modificati.");
      const { data, error } = await supabase.from("strength_workouts").update({ scheduled_date: date }).eq("id", workout.id).eq("strength_plan_id", id).eq("status", "planned").select("id").single();
      if (error || !data) throw new Error("Programma creato, ma non tutti i giorni sono stati salvati. Riprova per completare la pianificazione.");
    }));
  }
  return id;
}
