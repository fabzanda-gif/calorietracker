import { apiRequest } from "./client";

export interface LoggedMeal {
  id?: string | number | null;
  date: string;
  meal_type: string;
  name: string;
  base_name?: string | null;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  category?: string | null;
  notes?: string | null;
  [key: string]: unknown;
}

export interface MealsForDateResponse {
  date: string;
  count: number;
  items: LoggedMeal[];
}

export function getMealsForDate(
  dayDate: string,
  accessToken?: string | null,
): Promise<MealsForDateResponse> {
  return apiRequest<MealsForDateResponse>(
    `/meals/${encodeURIComponent(dayDate)}`,
    {
      accessToken,
    },
  );
}


export interface MealCreateInput {
  date: string;
  meal_type: string;
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  structured_ingredients?: Array<{
    ingredient_id: string;
    quantity: number;
    unit: string;
    quantity_g: number;
  }>;
}

export interface MealCreateResponse {
  created: boolean;
  item: LoggedMeal;
}

export function createMeal(
  input: MealCreateInput,
  accessToken?: string | null,
): Promise<MealCreateResponse> {
  return apiRequest<MealCreateResponse>(
    "/meals",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}
