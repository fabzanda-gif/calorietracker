import { apiRequest } from "./client";

export interface TrainingNutritionDay {
  date: string;
  training: {
    strength_completed: number;
    strength_planned: number;
    running_completed: number;
    running_planned: number;
  };
  training_context: "training_completed" | "training_planned" | "no_training_logged";
  meal_count: number;
  logged_macros: {
    calories_kcal: number;
    protein_g: number;
    carbs_g: number;
    fat_g: number;
  };
  protein_target_g: number | null;
  protein_remaining_g: number | null;
  protein_target_status: "not_configured" | "not_logged" | "met" | "below";
  note_key: string;
}
export interface TrainingNutritionWeek {
  start_date: string;
  end_date: string;
  days: TrainingNutritionDay[];
  summary: {
    training_days: number;
    completed_training_days: number;
    days_with_meals: number;
    days_with_meals_and_training: number;
    protein_goal_configured: boolean;
  };
  policy: {
    read_only: true;
    calorie_target_changed: false;
    macro_targets_changed: false;
    planned_activity_calories_added: false;
    source: string;
  };
  disclaimer: string;
}
export function getTrainingNutritionWeek(
  accessToken: string,
  startDate: string,
  days = 7,
): Promise<TrainingNutritionWeek> {
  const params = new URLSearchParams({
    start_date: startDate,
    days: String(days),
  });
  return apiRequest<TrainingNutritionWeek>(
    `/training-nutrition/week?${params.toString()}`,
    { accessToken, route: "heavy" },
  );
}
