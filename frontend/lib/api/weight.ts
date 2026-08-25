import { apiRequest } from "./client";

export interface WeightEntry {
  id: string | number;
  date: string;
  weight: number;
}

export interface WeightHistoryResponse {
  count: number;
  items: WeightEntry[];
}

export function getWeightHistory(
  accessToken?: string | null,
): Promise<WeightHistoryResponse> {
  return apiRequest<WeightHistoryResponse>(
    "/weight",
    {
      accessToken,
    },
  );
}

export function createWeight(
  input: {
    date: string;
    weight: number;
  },
  accessToken?: string | null,
): Promise<{
  created: boolean;
  item: WeightEntry | null;
}> {
  return apiRequest(
    "/weight",
    {
      method: "POST",
      accessToken,
      body: JSON.stringify(input),
    },
  );
}
