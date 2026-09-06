import { apiRequest } from "./client";

export interface ConfirmMealResponse {
  confirmed: boolean;
  item: Record<string, unknown>;
}

export interface ConfirmMealRecommendation {
  name: string;
  quantity: number | null;
  calories: number;
  protein_g?: number;
  carbs_g?: number;
  fat_g?: number;
  strategy?: string;
  components?: unknown;
  removed_components?: Array<Record<string, unknown>>;
}

export function confirmMealPrediction(
  dayDate: string,
  mealSlot: string,
  accessToken?: string | null,
  recommendation?: ConfirmMealRecommendation | null,
): Promise<ConfirmMealResponse> {
  return apiRequest<ConfirmMealResponse>(
    `/days/${encodeURIComponent(dayDate)}` +
      `/meals/${encodeURIComponent(mealSlot)}` +
      `/confirm`,
    {
      method: "POST",
      accessToken,
      body: recommendation
        ? JSON.stringify({
            recommendation,
          })
        : undefined,
    },
  );
}
