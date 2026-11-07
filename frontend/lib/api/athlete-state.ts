import { apiRequest } from "./client";

export interface AthleteStateWindow {
  completed_sessions: number;
  training_days: number;
  total_sets: number;
  volume_load_kg: number;
  reported_hard_sets: number;
  feelings_reported: number;
  total_duration_minutes: number;
}
export interface AthleteStateWeek {
  start: string;
  end: string;
  sessions: number;
  sets: number;
}
export interface AthleteStateExercise {
  exercise_id: string;
  name: string;
  movement_pattern: string | null;
  sessions: number;
  sets: number;
  best_load_kg: number;
  best_volume_set_kg: number;
  last_performed_date: string | null;
}
export interface AthleteState {
  as_of: string;
  window_days: number;
  source: string;
  scope: "strength_only";
  data_status: "limited" | "available";
  last_completed_date: string | null;
  days_since_last_completed: number | null;
  recent_7_days: AthleteStateWindow;
  previous_7_days: Pick<AthleteStateWindow, "completed_sessions" | "total_sets" | "volume_load_kg">;
  last_28_days: AthleteStateWindow;
  last_56_days: AthleteStateWindow;
  weekly: AthleteStateWeek[];
  target_sessions_per_week: number | null;
  consistency_ratio_last_4_weeks: number | null;
  most_logged_exercises: AthleteStateExercise[];
  quality: {
    weeks_with_training_last_4: number;
    sessions_with_sets: number;
    sessions_without_sets: number;
    history_truncated: boolean;
  };
  note: string;
}
export function getAthleteState(
  accessToken: string,
  asOf?: string,
): Promise<AthleteState> {
  const suffix = asOf ? `?as_of=${encodeURIComponent(asOf)}` : "";
  return apiRequest<AthleteState>(`/athlete-state${suffix}`, { accessToken, route: "heavy" });
}
