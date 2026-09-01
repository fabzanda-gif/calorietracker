import { apiRequest } from "./client";
import type {
  DayBudgetResponse,
  DayResponse,
  DecisionMode,
  MealOptionsResponse,
  NextMealResponse,
} from "./types";

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
  }>(
    `/daily-logs/${date}`,
    {
      method: "PATCH",
      accessToken,
      body: JSON.stringify(changes),
    },
  );
}
