import { apiRequest } from "./client";

export interface ConfirmMealResponse {
  confirmed: boolean;
  item: Record<string, unknown>;
}

export function confirmMealPrediction(
  dayDate: string,
  mealSlot: string,
  accessToken?: string | null,
): Promise<ConfirmMealResponse> {
  return apiRequest<ConfirmMealResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/meals/${encodeURIComponent(mealSlot)}` +
      `/confirm`,
    {
      method: "POST",
      accessToken,
    },
  );
}
