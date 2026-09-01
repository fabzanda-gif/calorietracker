import { apiRequest } from "./client";

export interface MealPrepItem {
  id: string;
  recipe_id: string;
  name: string;
  prepared_at: string;
  expires_at: string | null;
  portions_prepared: number;
  portions_remaining: number;
  calories_per_portion: number;
  protein_per_portion: number;
  carbs_per_portion: number;
  fat_per_portion: number;
  status: string;
  created_at: string;
  image_url: string | null;
}

export interface MealPrepResponse {
  count: number;
  items: MealPrepItem[];
}

export interface MealPrepCreate {
  recipe_id: string;
  prepared_at: string;
  portions_prepared: number;
  expires_at?: string | null;
}

export interface MealPrepConsumeResponse {
  updated: boolean;
  item: MealPrepItem;
}

export function getMealPrepInventory(
  accessToken: string,
  availableOnly = false,
): Promise<MealPrepResponse> {
  const query = new URLSearchParams();

  if (availableOnly) {
    query.set("available_only", "true");
  }

  const suffix = query.toString()
    ? `?${query.toString()}`
    : "";

  return apiRequest<MealPrepResponse>(
    `/meal-prep${suffix}`,
    {
      accessToken,
    },
  );
}

export function createMealPrep(
  accessToken: string,
  payload: MealPrepCreate,
): Promise<{
  created: boolean;
  item: MealPrepItem;
}> {
  return apiRequest(
    "/meal-prep",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(payload),
    },
  );
}

export interface MealPrepLogResponse {
  logged: boolean;
  meal: Record<string, unknown>;
  inventory: MealPrepItem;
}

export function logMealPrepPortion(
  accessToken: string,
  batchId: string,
  date: string,
  mealType: string,
): Promise<MealPrepLogResponse> {
  return apiRequest<MealPrepLogResponse>(
    `/meal-prep/${batchId}/log`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        date,
        meal_type: mealType,
      }),
    },
  );
}


export interface MealPrepDiscardResponse {
  updated: boolean;
  discarded: number;
  item: MealPrepItem;
}

export function discardMealPrepPortions(
  accessToken: string,
  batchId: string,
  portions = 1,
): Promise<MealPrepDiscardResponse> {
  return apiRequest<MealPrepDiscardResponse>(
    `/meal-prep/${batchId}/discard`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({ portions }),
    },
  );
}

export function consumeMealPrep(
  accessToken: string,
  batchId: string,
  portions = 1,
): Promise<MealPrepConsumeResponse> {
  return apiRequest<MealPrepConsumeResponse>(
    `/meal-prep/${batchId}/consume`,
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({ portions }),
    },
  );
}
