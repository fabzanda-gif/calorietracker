import { apiRequest } from "./client";

export interface NutritionProgressItem {
  date: string;
  consumed_kcal: number;
  budget_kcal: number | null;
  difference_kcal: number | null;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  activity_kcal: number;
  breakfast_kcal: number;
  lunch_kcal: number;
  dinner_kcal: number;
  other_kcal: number;
  meal_count: number;
  activity_count: number;
}

export interface NutritionProgressSummary {
  logged_days: number;
  average_consumed_kcal: number;
  average_budget_kcal: number | null;
  days_within_budget: number;
  days_with_budget: number;
}

export interface NutritionProgressResponse {
  start_date: string;
  end_date: string;
  count: number;
  summary: NutritionProgressSummary;
  items: NutritionProgressItem[];
}

export function getNutritionProgress(
  startDate: string,
  endDate: string,
  accessToken?: string | null,
): Promise<NutritionProgressResponse> {
  const params = new URLSearchParams({
    start_date: startDate,
    end_date: endDate,
  });

  return apiRequest<NutritionProgressResponse>(
    `/progress/nutrition?${params.toString()}`,
    {
      accessToken,
    },
  );
}
