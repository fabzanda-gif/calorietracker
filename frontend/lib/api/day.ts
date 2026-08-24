import { apiRequest } from "./client";
import type {
  DayResponse,
  DecisionMode,
  MealOptionsResponse,
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
