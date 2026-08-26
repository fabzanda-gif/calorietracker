import { apiRequest } from "./client";

export interface StructuredMealIngredient {
  id?: string | number | null;
  meal_id?: string | number | null;
  ingredient_id: string;
  name_snapshot?: string | null;
  quantity: number;
  unit: string;
  quantity_g: number;
  original_quantity_g?: number;
  calories?: number;
  protein?: number;
  carbs?: number;
  fat?: number;
}

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
  is_reusable?: boolean | null;
  notes?: string | null;
  quantity?: number | null;
  is_per_100g?: boolean | null;
  base_calories?: number | null;
  base_protein?: number | null;
  base_carbs?: number | null;
  base_fat?: number | null;
  structured_ingredients?: StructuredMealIngredient[];
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


export interface StructuredMealCreateIngredient {
  ingredient_id: string;
  quantity: number;
  unit: string;
  quantity_g: number;
}

export interface MealCreateInput {
  date: string;
  meal_type: string;
  name: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  is_reusable?: boolean;
  base_name?: string | null;
  quantity?: number | null;
  is_per_100g?: boolean | null;
  base_calories?: number | null;
  base_protein?: number | null;
  base_carbs?: number | null;
  base_fat?: number | null;
  structured_ingredients?: Array<{
    ingredient_id: string;
    quantity: number;
    unit: string;
    quantity_g: number;
  }>;
}

export interface MealUpdateInput {
  meal_type?: string;
  name?: string;
  calories?: number;
  protein?: number;
  carbs?: number;
  fat?: number;
  is_reusable?: boolean;
  base_name?: string | null;
  quantity?: number | null;
  is_per_100g?: boolean | null;
  base_calories?: number | null;
  base_protein?: number | null;
  base_carbs?: number | null;
  base_fat?: number | null;
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


export function getMeal(
  mealId: string | number,
  accessToken?: string | null,
): Promise<{ item: LoggedMeal }> {
  return apiRequest<{ item: LoggedMeal }>(
    `/meals/item/${encodeURIComponent(String(mealId))}`,
    {
      accessToken,
    },
  );
}

export function updateMeal(
  mealId: string | number,
  input: MealUpdateInput,
  accessToken?: string | null,
): Promise<{
  updated: boolean;
  structured: boolean;
  item: LoggedMeal;
  meal_ingredients?: StructuredMealIngredient[];
}> {
  return apiRequest(
    `/meals/${encodeURIComponent(String(mealId))}`,
    {
      method: "PATCH",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}


export function deleteMeal(
  mealId: string | number,
  accessToken?: string | null,
): Promise<{
  deleted: boolean;
  id: string;
}> {
  return apiRequest(
    `/meals/${encodeURIComponent(String(mealId))}`,
    {
      method: "DELETE",
      accessToken,
    },
  );
}


export interface ConversationalMealPreviewItem {
  name: string;
  quantity: number;
  unit: string;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  estimated: boolean;
  uncertainty?: string | null;
}

export interface ConversationalMealPreview {
  status: "preview";
  meal_type: string;
  original_text: string;
  items: ConversationalMealPreviewItem[];
  totals: {
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
  };
  needs_review: boolean;
  requires_confirmation: boolean;
}

export function previewConversationalMeal(
  text: string,
  mealType: string,
  accessToken?: string | null,
): Promise<ConversationalMealPreview> {
  return apiRequest<ConversationalMealPreview>(
    "/meals/conversational/preview",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify({
        text,
        meal_type: mealType,
      }),
    },
  );
}
