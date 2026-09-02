import { apiRequest } from "./client";
import type {
  ActivityMovementSummary,
} from "./activities";
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
  accessToken?: string | null,
): Promise<DayBriefingResponse> {
  const query = new URLSearchParams({
    moment,
    mode,
    hour: String(hour),
  });

  return apiRequest<DayBriefingResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/briefing?${query.toString()}`,
    {
      accessToken,
    },
  );
}
