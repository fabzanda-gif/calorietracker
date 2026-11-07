import { apiRequest } from "./client";

export type ProgramV2Goal = "strength" | "hypertrophy" | "general_fitness";

export interface ProgramV2Request {
  start_date: string;
  goal: ProgramV2Goal;
  total_weeks: number;
  allowed_equipment: string[];
  replace_active?: boolean;
}
export interface ProgramV2Exercise {
  position: number;
  exercise_id: string;
  exercise_name: string;
  movement_pattern: string;
  target_sets: number;
  target_reps_min: number;
  target_reps_max: number;
  target_rir: number;
  rest_seconds: number;
  approved_for_generation: true;
}
export interface ProgramV2Workout {
  scheduled_date: string;
  training_week: number;
  workout_index: number;
  title: string;
  focus: string;
  estimated_duration_minutes: number;
  exercises: ProgramV2Exercise[];
}
export interface ProgramV2Preview {
  generator_version: 2;
  preview: true;
  ready_for_activation: boolean;
  warnings: string[];
  missing_movement_patterns: string[];
  approved_catalog_count: number;
  goal: ProgramV2Goal;
  experience_level: string;
  sessions_per_week: number;
  session_duration_minutes: number;
  program_style: string;
  start_date: string;
  total_weeks: number;
  workout_count: number;
  athlete_data_status: "available" | "limited" | "unavailable";
  workouts: ProgramV2Workout[];
}
export interface ProgramV2CreateResponse {
  created: true;
  plan: { id: string };
  workout_count: number;
  exercise_count: number;
  replaced_plan_ids: string[];
}
export function previewProgramV2(
  accessToken: string,
  input: ProgramV2Request,
): Promise<ProgramV2Preview> {
  return apiRequest<ProgramV2Preview>("/strength/plans/v2/preview", {
    accessToken,
    route: "heavy",
    method: "POST",
    body: JSON.stringify(input),
  });
}
export function createProgramV2(
  accessToken: string,
  input: ProgramV2Request,
): Promise<ProgramV2CreateResponse> {
  return apiRequest<ProgramV2CreateResponse>("/strength/plans/v2", {
    accessToken,
    route: "heavy",
    method: "POST",
    body: JSON.stringify(input),
  });
}
