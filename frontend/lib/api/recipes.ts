import { apiRequest } from "./client";

export interface StructuredRecipeIngredient {
  id?: string;
  recipe_id?: string;
  ingredient_id: string;
  quantity: number;
  unit: string;
  quantity_g: number;
  ingredients?: {
    id: string;
    name: string;
    normalized_name: string;
    calories_per_100g: number;
    protein_per_100g: number;
    carbs_per_100g: number;
    fat_per_100g: number;
    default_unit: string;
  };
}

export interface Recipe {
  preparation?: string | null;
  id: string;
  name: string;
  meal_type?: string | null;
  category?: string | null;
  recipe_servings?: number | null;
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
  notes?: string | null;
  ingredients_json?: unknown;
  image_url?: string | null;
  taste_rating?: number | null;
  ease_rating?: number | null;
  structured_ingredients?: StructuredRecipeIngredient[];
}

export interface RecipesResponse {
  count: number;
  items: Recipe[];
}

export interface RecipeWriteInput {
  name: string;
  meal_type?: string | null;
  category?: string | null;
  recipe_servings?: number | null;
  image_url?: string | null;
  notes?: string | null;
  taste_rating?: number | null;
  ease_rating?: number | null;
  structured_ingredients: Array<{
    ingredient_id: string;
    quantity: number;
    unit: string;
    quantity_g: number;
  }>;
}

export async function getRecipes(
  accessToken?: string | null,
): Promise<RecipesResponse> {
  return apiRequest<RecipesResponse>(
    "/recipes",
    {
      accessToken,
    },
  );
}

export async function getAvailableRecipes(
  accessToken?: string | null,
): Promise<RecipesResponse> {
  return apiRequest<RecipesResponse>(
    "/recipes/available",
    {
      accessToken,
    },
  );
}

export async function getRecipe(
  recipeId: string,
  accessToken?: string | null,
): Promise<{ item: Recipe }> {
  return apiRequest(
    `/recipes/${encodeURIComponent(recipeId)}`,
    {
      accessToken,
    },
  );
}

export async function createRecipe(
  input: RecipeWriteInput,
  accessToken?: string | null,
): Promise<{ created: boolean; item: Recipe }> {
  return apiRequest(
    "/recipes",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export async function updateRecipe(
  recipeId: string,
  input: Partial<RecipeWriteInput>,
  accessToken?: string | null,
): Promise<{ updated: boolean; item: Recipe }> {
  return apiRequest(
    `/recipes/${encodeURIComponent(recipeId)}`,
    {
      method: "PATCH",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}

export interface LegacyRecipeMigrationResult {
  migrated: boolean;
  migrated_recipes: number;
  created_ingredients: number;
  created_links: number;
  skipped_recipes: number;
}

export async function migrateLegacyRecipes(
  accessToken?: string | null,
): Promise<LegacyRecipeMigrationResult> {
  return apiRequest<LegacyRecipeMigrationResult>(
    "/recipes/migrate-legacy",
    {
      method: "POST",
      accessToken,
    },
  );
}
