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
