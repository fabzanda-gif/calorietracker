import { apiRequest } from "./client";

export interface AdaptiveMacroPreview {
  as_of: string;
  start_date: string;
  lookback_days: number;
  goal_mode: "loss" | "gain" | "maintenance";
  current_goal_adjustment_kcal: number;
  status:
    | "insufficient_data"
    | "maintenance_observation"
    | "proposal_available"
    | "within_range";
  reasons: string[];
  observed: {
    logged_meal_days: number;
    weight_measurements: number;
    weight_observation_span_days: number;
    weight_change_pct_per_week: number | null;
    training_days_with_meals: number;
    non_training_days_with_meals: number;
    mean_logged_calories_kcal: number | null;
    mean_logged_protein_g: number | null;
    mean_training_day_carbs_g: number | null;
    mean_other_day_carbs_g: number | null;
    protein_target_g: number | null;
  };
  proposal: null | {
    kind: "adjust_goal_energy";
    goal_mode: "loss" | "gain";
    before_goal_adjustment_kcal: number;
    proposed_goal_adjustment_kcal: number;
    estimated_budget_change_kcal: number;
    requires_confirmation: true;
    reason: string;
  };
  preview_id: string;
  policy: {
    auto_apply: false;
    missing_meals_are_not_zero_intake: true;
    no_unverified_macro_targets: true;
    max_adjustment_step_kcal: number;
  };
}

export interface AdaptiveMacroApplyResponse {
  applied: true;
  updated_goal_mode: "loss" | "gain";
  updated_goal_adjustment_kcal: number;
}

export function getAdaptiveMacroPreview(
  accessToken: string,
): Promise<AdaptiveMacroPreview> {
  return apiRequest<AdaptiveMacroPreview>(
    "/adaptive-macros/preview",
    { accessToken, route: "heavy" },
  );
}

export function applyAdaptiveMacroProposal(
  accessToken: string,
  previewId: string,
): Promise<AdaptiveMacroApplyResponse> {
  return apiRequest<AdaptiveMacroApplyResponse>(
    "/adaptive-macros/apply",
    {
      method: "POST",
      accessToken,
      route: "heavy",
      body: JSON.stringify({
        preview_id: previewId,
        confirm: true,
        logging_complete_confirmed: true,
      }),
    },
  );
}
