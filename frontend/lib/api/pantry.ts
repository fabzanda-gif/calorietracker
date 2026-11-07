import { apiRequest } from "./client";

export interface PantryItem {
  id: string;
  user_id: string;
  ingredient_id: string;
  ingredient_name: string | null;
  quantity: number;
  unit: string;
  quantity_mode: "weight" | "portion";
  grams_per_portion: number | null;
  expires_at: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PantryResponse {
  count: number;
  items: PantryItem[];
}

export interface PantryInput {
  ingredient_id: string;
  quantity: number;
  unit: string;
  quantity_mode: "weight" | "portion";
  grams_per_portion?: number | null;
  expires_at?: string | null;
}

export function getPantry(
  accessToken: string,
): Promise<PantryResponse> {
  return apiRequest<PantryResponse>("/pantry", {
    accessToken,
  });
}

export function createPantryItem(
  accessToken: string,
  payload: PantryInput,
): Promise<{ created: boolean; item: PantryItem }> {
  return apiRequest("/pantry", {
    method: "POST",
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function updatePantryItem(
  accessToken: string,
  itemId: string,
  payload: Partial<Omit<PantryInput, "ingredient_id">>,
): Promise<{ updated: boolean; item: PantryItem }> {
  return apiRequest(`/pantry/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    accessToken,
    body: JSON.stringify(payload),
  });
}

export function deletePantryItem(
  accessToken: string,
  itemId: string,
): Promise<{ deleted: boolean; id: string }> {
  return apiRequest(`/pantry/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
    accessToken,
  });
}
