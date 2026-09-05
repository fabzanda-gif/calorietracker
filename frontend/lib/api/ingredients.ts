import { apiRequest } from "./client";

export interface Ingredient {
  id: string;
  user_id: string;
  name: string;
  normalized_name: string;
  calories_per_100g: number;
  protein_per_100g: number;
  carbs_per_100g: number;
  fat_per_100g: number;
  default_unit: string;
  grams_per_unit: number | null;
  default_quantity: number | null;
  kind:
    | "ingredient"
    | "product"
    | "prepared_food";
  meal_slots: Array<
    | "breakfast"
    | "lunch"
    | "snack"
    | "dinner"
  >;
}

export interface IngredientsResponse {
  count: number;
  items: Ingredient[];
}

export interface IngredientCreateInput {
  name: string;
  calories_per_100g: number;
  protein_per_100g: number;
  carbs_per_100g: number;
  fat_per_100g: number;
  default_unit?: string;
  grams_per_unit?: number | null;
  default_quantity?: number | null;
  kind?:
    | "ingredient"
    | "product"
    | "prepared_food";
  meal_slots?: Array<
    | "breakfast"
    | "lunch"
    | "snack"
    | "dinner"
  >;
}

export async function getIngredients(
  accessToken?: string | null,
): Promise<IngredientsResponse> {
  return apiRequest<IngredientsResponse>(
    "/ingredients",
    {
      accessToken,
    },
  );
}

export async function createIngredient(
  input: IngredientCreateInput,
  accessToken?: string | null,
): Promise<{ created: boolean; item: Ingredient }> {
  return apiRequest(
    "/ingredients",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export async function updateIngredient(
  ingredientId: string,
  input: Partial<IngredientCreateInput>,
  accessToken?: string | null,
): Promise<{ item: Ingredient }> {
  return apiRequest(`/ingredients/${encodeURIComponent(ingredientId)}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(input),
  });
}

export async function deleteIngredient(
  ingredientId: string,
  accessToken?: string | null,
): Promise<{ deleted: boolean }> {
  return apiRequest(`/ingredients/${encodeURIComponent(ingredientId)}`, {
    method: "DELETE",
    accessToken,
  });
}

/* NUTRITION LABEL SCAN API START */

export interface NutritionLabelScanResult {
  name: string | null;
  basis:
    | "per_100g"
    | "per_serving"
    | "unknown";
  serving_size_g: number | null;
  calories: number | null;
  protein: number | null;
  carbs: number | null;
  fat: number | null;
  confidence:
    | "high"
    | "medium"
    | "low";
  notes: string | null;
  ready_for_form: boolean;
}

export async function scanNutritionLabel(
  input: {
    content_base64: string;
    mime_type: string;
  },
  accessToken?: string | null,
): Promise<{
  result: NutritionLabelScanResult;
}> {
  return apiRequest(
    "/ingredients/scan-label",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

/* NUTRITION LABEL SCAN API END */
