import { apiRequest } from "./client";
import type {
  ActivityMovementSummary,
} from "./activities";
import type {
  DayBudgetResponse,
  DayResponse,
  DecisionMode,
  HomeCoreResponse,
  MealOptionsResponse,
  NextMealResponse,
  TrainingNutritionResponse,
} from "./types";

export type HomeSummaryMeal = {
  id?: string | number | null;
  meal_type: string;
  name: string;
  calories?: number | null;
  protein?: number | null;
};

export type HomeSummaryActivity = {
  id?: string | number | null;
  date: string;
  activity_name: string;
  burned_calories?: number | null;
  duration_seconds?: number | null;
  distance_meters?: number | null;
};

export type HomeSummaryResponse = {
  date: string;
  context: string | null;
  special_period: {
    id?: string;
    period_type: "vacation" | "illness";
    start_date: string;
    end_date: string;
    notes?: string | null;
  } | null;
  hero: {
    kind: string;
    title: string;
    message: string;
    icon: string;
  };
  budget: {
    daily_budget_kcal: number;
    consumed_kcal: number;
    available_kcal: number;
    maintenance_kcal: number;
    protein_consumed_g: number;
    protein_target_g: number | null;
    protein_remaining_g: number | null;
  } | null;
  profile_goal: {
    goal_mode: string;
    goal_adjustment_kcal: number;
    bmr: number | null;
    protein_target_g: number | null;
    profile_complete_for_budget: boolean;
  };
  latest_weight: {
    id?: string | number;
    date: string;
    weight: number;
  } | null;
  meals: HomeSummaryMeal[];
  activities: HomeSummaryActivity[];
  planned_today: Array<Record<string, unknown>>;
  planned_tomorrow: Array<Record<string, unknown>>;
  meta: {
    history_days_used: number;
    ai_calls: number;
    average_activity_kcal_7d: number;
  };
};

export function getHomeSummary(
  dayDate: string,
  accessToken?: string | null,
): Promise<HomeSummaryResponse> {
  return apiRequest<HomeSummaryResponse>(
    `/home-summary/${encodeURIComponent(dayDate)}`,
    {
      accessToken,
      route: "heavy",
    },
  );
}

export function getHomeCore(
  dayDate: string,
  accessToken?: string | null,
): Promise<HomeCoreResponse> {
  return apiRequest<HomeCoreResponse>(
    `/days/${encodeURIComponent(dayDate)}/home-core`,
    {
      accessToken,
    },
  );
}

export function getDay(
  dayDate: string,
  accessToken?: string | null,
): Promise<DayResponse> {
  return apiRequest<DayResponse>(
    `/days/${encodeURIComponent(dayDate)}`,
    {
      accessToken,
    },
  );
}

export function getNextMeal(
  dayDate: string,
  accessToken?: string | null,
): Promise<NextMealResponse> {
  return apiRequest<NextMealResponse>(
    `/days/${encodeURIComponent(dayDate)}/next-meal`,
    {
      accessToken,
    },
  );
}

export function getTrainingNutrition(
  dayDate: string,
  accessToken?: string | null,
): Promise<TrainingNutritionResponse> {
  return apiRequest<TrainingNutritionResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/training-nutrition`,
    {
      accessToken,
    },
  );
}

export function getDayBudget(
  dayDate: string,
  accessToken?: string | null,
): Promise<DayBudgetResponse> {
  return apiRequest<DayBudgetResponse>(
    `/days/${encodeURIComponent(dayDate)}/budget`,
    {
      accessToken,
    },
  );
}

export function getMealOptions(
  dayDate: string,
  mealSlot: string,
  mode: DecisionMode = "auto",
  accessToken?: string | null,
): Promise<MealOptionsResponse> {
  const query = new URLSearchParams({
    mode,
  });

  return apiRequest<MealOptionsResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/meals/${encodeURIComponent(mealSlot)}` +
      `/options?${query.toString()}`,
    {
      accessToken,
    },
  );
}

export type DailyLogUpdate = {
  weight?: number | null;
  steps?: number | null;
  day_type?: string | null;
  activity_plan?: string | null;
};

export async function updateDailyLog(
  accessToken: string,
  date: string,
  changes: DailyLogUpdate,
) {
  return apiRequest<{
    updated: boolean;
    date: string;
    item: Record<string, unknown> | null;
    movement?: ActivityMovementSummary | null;
  }>(
    `/daily-logs/${date}`,
    {
      method: "PATCH",
      accessToken,
      body: JSON.stringify(changes),
    },
  );
}


export type DayBriefingMode =
  | "standard"
  | "zero";

export type DayBriefingMoment =
  | "morning"
  | "afternoon"
  | "evening";

export type DayBriefingResponse = {
  date: string;
  mode: DayBriefingMode;
  message: string;
  source: "ai" | "fallback";
  cached: boolean;
};

export function getDayBriefing(
  dayDate: string,
  moment: DayBriefingMoment,
  mode: DayBriefingMode = "standard",
  hour: number = new Date().getHours(),
  language: "it" | "en" | "nl" | "fr" = "it",
  accessToken?: string | null,
): Promise<DayBriefingResponse> {
  const query = new URLSearchParams({
    moment,
    mode,
    hour: String(hour),
    language,
  });

  return apiRequest<DayBriefingResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/briefing?${query.toString()}`,
    {
      accessToken,
    },
  );
}
