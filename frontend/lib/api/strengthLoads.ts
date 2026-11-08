import { supabase } from "@/lib/supabase/client";
import type { StrengthWorkoutExercise } from "./strength";

export type StrengthLoadProfile = {
  user_id: string; exercise_ref: string; exercise_name: string;
  one_rep_max_kg: number | null; working_load_kg: number; reference_reps: number;
  reserve_reps: number; source: "known_max" | "guided_test"; updated_at: string;
};
export function exerciseRef(exercise: StrengthWorkoutExercise): string {
  return exercise.exercise_id ? `library:${exercise.exercise_id}` : `legacy:${exercise.exercise_key}:${exercise.exercise_name.toLowerCase()}`;
}
export async function getStrengthLoadProfiles(userId: string): Promise<StrengthLoadProfile[]> {
  const { data, error } = await supabase.from("strength_load_profiles")
    .select("user_id,exercise_ref,exercise_name,one_rep_max_kg,working_load_kg,reference_reps,reserve_reps,source,updated_at").eq("user_id", userId);
  if (error) throw error;
  return data ?? [];
}
export async function saveStrengthLoadProfile(profile: StrengthLoadProfile): Promise<void> {
  const { error } = await supabase.from("strength_load_profiles").upsert(profile, { onConflict: "user_id,exercise_ref" });
  if (error) throw error;
}
