import { apiRequest } from "./client";

export type CoachPriority =
  | "gym"
  | "balanced"
  | "running";

export type CoachDecision =
  | "proposed"
  | "auto_applied"
  | "accepted"
  | "dismissed";

export type CoachSeverity =
  | "low"
  | "moderate"
  | "high";

export type CoachAction =
  | "reduce_load"
  | "reduce_volume"
  | "reduce_running_load"
  | "reschedule";

export interface CoachLoadEvent {
  source_kind:
    | "activity"
    | "strength_workout";
  source_id: string;
  date: string;
  title?: string | null;
  modality:
    | "running"
    | "cardio"
    | "strength";
  scope:
    | "upper"
    | "lower"
    | "full_body"
    | "cardio";
  intensity:
    | "low"
    | "moderate"
    | "high";
  load_score: number;
  duration_minutes?: number;
  distance_meters?: number;
  workout_kind?: "planned" | "free";
}

export interface CoachAdjustment {
  id: string;
  source_kind:
    | "activity"
    | "strength_workout";
  source_id: string;
  source_date: string;
  target_kind:
    | "strength_workout"
    | "planned_activity";
  target_id: string;
  target_date: string;
  action: CoachAction;
  severity: CoachSeverity;
  scope:
    | "upper"
    | "lower"
    | "full_body"
    | "cardio";
  decision: CoachDecision;
  title: string;
  message: string;
  proposed_changes: Record<
    string,
    unknown
  >;
  before_state?: Record<
    string,
    unknown
  > | null;
  after_state?: Record<
    string,
    unknown
  > | null;
  created_at?: string;
  updated_at?: string;
}

export interface CoachRecoveryAlert {
  kind: "planned_activity" | "strength_workout";
  session_id: string;
  scheduled_date: string;
  title: string;
  message: string;
  requires_approval: boolean;
  suggested_date: string | null;
  is_race: boolean;
  recovery_days: number;
}

export interface CoachReconcileResponse {
  policy: CoachPriority;
  as_of: string;
  window: {
    recent_start: string;
    future_end: string;
  };
  load_events: CoachLoadEvent[];
  recovery_alerts?: CoachRecoveryAlert[];
  adjustments: CoachAdjustment[];
  history: CoachAdjustment[];
  summary: {
    events: number;
    proposed: number;
    auto_applied: number;
  };
}

export function reconcileTrainingCoach(
  asOf: string,
  accessToken?: string | null,
): Promise<CoachReconcileResponse> {
  return apiRequest<CoachReconcileResponse>(
    "/coach/reconcile",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        as_of: asOf,
      }),
    },
  );
}

export function applyCoachAdjustment(
  id: string,
  accessToken?: string | null,
): Promise<{
  applied: true;
  adjustment: CoachAdjustment;
  after_state: unknown;
}> {
  return apiRequest(
    (
      "/coach/adjustments/" +
      encodeURIComponent(id) +
      "/apply"
    ),
    {
      method: "POST",
      accessToken,
    },
  );
}

export function dismissCoachAdjustment(
  id: string,
  accessToken?: string | null,
): Promise<{
  dismissed: true;
  adjustment: CoachAdjustment;
}> {
  return apiRequest(
    (
      "/coach/adjustments/" +
      encodeURIComponent(id) +
      "/dismiss"
    ),
    {
      method: "POST",
      accessToken,
    },
  );
}


export function getCoachPreferences(
  accessToken?: string | null,
): Promise<{
  priority: CoachPriority;
}> {
  return apiRequest(
    "/coach/preferences",
    {
      accessToken,
    },
  );
}

export function updateCoachPreferences(
  priority: CoachPriority,
  accessToken?: string | null,
): Promise<{
  priority: CoachPriority;
}> {
  return apiRequest(
    "/coach/preferences",
    {
      method: "PUT",
      accessToken,
      body: JSON.stringify({
        priority,
      }),
    },
  );
}

export function applyCoachRecovery(
  kind: CoachRecoveryAlert["kind"],
  id: string,
  originalDate: string,
  suggestedDate: string,
  accessToken?: string | null,
): Promise<{ applied: true; item: unknown }> {
  return apiRequest(
    "/coach/recovery/" +
      encodeURIComponent(kind) +
      "/" +
      encodeURIComponent(id) +
      "/apply",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        original_date: originalDate,
        suggested_date: suggestedDate,
      }),
    },
  );
}
