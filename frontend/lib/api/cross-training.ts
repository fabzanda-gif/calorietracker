import { apiRequest } from "./client";

export type CrossTrainingEvent = {
  id: string;
  source_id: string;
  date: string;
  modality: "strength" | "running";
  status: "planned" | "completed";
  title: string;
  scope: "lower" | "upper" | "full_body" | "unknown";
  quality: boolean;
  is_race: boolean;
};

export interface CrossTrainingConflict {
  id: string;
  date: string;
  severity: "high" | "moderate";
  gap_days: number;
  gym_event_id: string;
  running_event_id: string;
  race_protected: boolean;
  message_key: "protect_race" | "review_lower_and_quality_run";
  suggested_action: "review_gym_schedule" | "review_session_spacing";
  requires_confirmation: true;
}
export interface CrossTrainingTimeline {
  start_date: string;
  end_date: string;
  priority: "gym" | "running" | "balanced";
  timeline: {
    date: string;
    events: CrossTrainingEvent[];
    running_count: number;
    strength_count: number;
  }[];
  conflicts: CrossTrainingConflict[];
  summary: {
    running_sessions: number;
    strength_sessions: number;
    potential_conflicts: number;
  };
  policy: {
    read_only: true;
    auto_rescheduled: false;
    auto_changed_load: false;
    races_unchanged: true;
    completed_workouts_unchanged: true;
  };
  note: string;
}

export function getCrossTrainingTimeline(
  accessToken: string,
  startDate: string,
  days = 14,
): Promise<CrossTrainingTimeline> {
  const qs = new URLSearchParams({
    start_date: startDate,
    days: String(days),
  });
  return apiRequest<CrossTrainingTimeline>(
    `/cross-training/timeline?${qs.toString()}`,
    { accessToken, route: "heavy" },
  );
}
